#self+ ImportanceMapJSCC perception model wrapper: PointPillars + dispatch to ImportanceMapJSCC/SComCP fuse variants
import torch.nn as nn

from opencood.models.sub_modules.base_bev_backbone import BaseBEVBackbone
from opencood.models.fuse_modules.importance_map_jscc_fuse import ImportanceMapJSCC
from opencood.models.sub_modules.downsample_conv import DownsampleConv
from opencood.models.sub_modules.naive_compress import NaiveCompressor
from opencood.models.sub_modules.pillar_vfe import PillarVFE
from opencood.models.sub_modules.point_pillar_scatter import PointPillarScatter


class PointPillarImportanceMapJscc(nn.Module):
    def __init__(self, args):
        super(PointPillarImportanceMapJscc, self).__init__()
        self.max_cav = args['max_cav']
        # Pillar VFE
        self.pillar_vfe = PillarVFE(args['pillar_vfe'],
                                    num_point_features=4,
                                    voxel_size=args['voxel_size'],
                                    point_cloud_range=args['lidar_range'])
        self.scatter = PointPillarScatter(args['point_pillar_scatter'])
        self.backbone = BaseBEVBackbone(args['base_bev_backbone'], 64)

        # Used to down-sample the feature map for efficient computation
        if 'shrink_header' in args:
            self.shrink_flag = True
            self.shrink_conv = DownsampleConv(args['shrink_header'])
        else:
            self.shrink_flag = False

        if args['compression']:
            self.compression = True
            self.naive_compressor = NaiveCompressor(256, args['compression'])
        else:
            self.compression = False

        fuse_cfg = args.get('importance_map_jscc_fusion', args['where2comm_fusion'])
        if str(fuse_cfg.get('variant', '')).lower() == 'scomcp':
            # Faithful SComCP variant: cross-attention selector + transformer-CA codec.
            from opencood.models.fuse_modules.scomcp_fuse import SComCPFuse
            self.fusion_net = SComCPFuse(fuse_cfg)
        else:
            self.fusion_net = ImportanceMapJSCC(fuse_cfg)
        self.multi_scale = args['where2comm_fusion']['multi_scale']

        self.cls_head = nn.Conv2d(args['head_dim'], args['anchor_number'], kernel_size=1)
        self.reg_head = nn.Conv2d(args['head_dim'], 7 * args['anchor_number'], kernel_size=1)

        if args['backbone_fix']:
            self.backbone_fix()

        # Three-stage training support (paper Algorithm 1): freeze submodules by
        # name so a single train script can run stage1 (selector only),
        # stage2 (codec only) and stage3 (joint, no freeze).
        self.freeze_stage(args.get('freeze', []))

    def freeze_stage(self, freeze_list):
        """Freeze named submodule groups. Names: backbone, heads, selector, codec."""
        if not freeze_list:
            return
        groups = {
            'backbone': [self.pillar_vfe, self.scatter, self.backbone]
                        + ([self.shrink_conv] if self.shrink_flag else [])
                        + ([self.naive_compressor] if self.compression else []),
            'heads': [self.cls_head, self.reg_head],
            'selector': [getattr(self.fusion_net, 'importance_map', None)],
            'codec': [getattr(self.fusion_net, 'semantic_codec', None)],
            'fusion': [getattr(self.fusion_net, 'fuse_modules', None)],
        }
        for name in freeze_list:
            for mod in groups.get(name, []):
                if mod is None:
                    continue
                for p in mod.parameters():
                    p.requires_grad = False
        print('[SComCP] frozen submodule groups: %s' % freeze_list)

    def backbone_fix(self):
        """
        Fix the parameters of backbone during finetune on timedelay.
        """

        for p in self.pillar_vfe.parameters():
            p.requires_grad = False

        for p in self.scatter.parameters():
            p.requires_grad = False

        for p in self.backbone.parameters():
            p.requires_grad = False

        if self.compression:
            for p in self.naive_compressor.parameters():
                p.requires_grad = False
        if self.shrink_flag:
            for p in self.shrink_conv.parameters():
                p.requires_grad = False

        for p in self.cls_head.parameters():
            p.requires_grad = False
        for p in self.reg_head.parameters():
            p.requires_grad = False

    def forward(self, data_dict):
        voxel_features = data_dict['processed_lidar']['voxel_features']
        voxel_coords = data_dict['processed_lidar']['voxel_coords']
        voxel_num_points = data_dict['processed_lidar']['voxel_num_points']
        record_len = data_dict['record_len']
        pairwise_t_matrix = data_dict['pairwise_t_matrix']

        batch_dict = {'voxel_features': voxel_features,
                      'voxel_coords': voxel_coords,
                      'voxel_num_points': voxel_num_points,
                      'record_len': record_len}
        # n, 4 -> n, c
        batch_dict = self.pillar_vfe(batch_dict)
        # n, c -> N, C, H, W
        batch_dict = self.scatter(batch_dict)
        batch_dict = self.backbone(batch_dict)

        # N, C, H', W': [N, 256, 48, 176]
        spatial_features_2d = batch_dict['spatial_features_2d']
        # Down-sample feature to reduce memory
        if self.shrink_flag:
            spatial_features_2d = self.shrink_conv(spatial_features_2d)

        psm_single = self.cls_head(spatial_features_2d)

        # Compressor
        if self.compression:
            # The ego feature is also compressed
            spatial_features_2d = self.naive_compressor(spatial_features_2d)

        if self.multi_scale:
            # Bypass communication cost, communicate at high resolution, neither shrink nor compress
            fused_feature, communication_rates = self.fusion_net(batch_dict['spatial_features'],
                                                                 psm_single,
                                                                 record_len,
                                                                 pairwise_t_matrix,
                                                                 self.backbone)
            if self.shrink_flag:
                fused_feature = self.shrink_conv(fused_feature)
        else:
            fused_feature, communication_rates = self.fusion_net(spatial_features_2d,
                                                                 psm_single,
                                                                 record_len,
                                                                 pairwise_t_matrix)

        psm = self.cls_head(fused_feature)
        rm = self.reg_head(fused_feature)

        output_dict = {'psm': psm, 'rm': rm, 'com': communication_rates}

        rec_loss = getattr(self.fusion_net, 'last_rec_loss', None)
        if rec_loss is not None:
            output_dict['rec_loss'] = rec_loss

        # Paper-CR diagnostics for importance-map JSCC reproduction.
        # These outputs do not change the model; they only expose internal statistics.
        for _debug_name in [
            'last_paper_cr_target',
            'last_paper_cr_actual',
            'last_paper_k',
            'last_paper_hw',
            'last_importance_score',
            'last_importance_mask',
            'last_com_including_ego',
            'last_remote_payload_cr_actual',
            'last_remote_payload_tokens',
            'last_remote_payload_total_tokens',
        ]:
            _debug_value = getattr(self.fusion_net, _debug_name, None)
            if _debug_value is None:
                continue

            _out_name = _debug_name.replace('last_', '')

            if hasattr(_debug_value, 'detach'):
                output_dict[_out_name] = _debug_value
            else:
                output_dict[_out_name] = psm.new_tensor(float(_debug_value))

        return output_dict
