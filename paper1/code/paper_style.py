#self+ Unified IEEE-style matplotlib settings for all CA-TOSG paper figures.
"""Import and call apply() at the top of every figure script so all figures share
one publication look: serif font matching the IEEE body text, consistent sizes,
clean lines, a fixed colour palette, and standard column widths.

Usage (works from any script depth):
    import paper_style as ps; ps.apply()
    fig, ax = plt.subplots(figsize=(ps.COL, 2.6))
"""
import matplotlib

# IEEE column geometry (inches)
COL = 3.5      # single-column width
DCOL = 7.16    # double-column (full text) width

# fixed, colour-blind-friendly palette used consistently across figures
C_L = '#0072B2'      # object-level L      (blue)
C_C16 = '#D55E00'    # feature-level C16   (vermillion)
C_C256 = '#E69F00'   # feature-level C256  (orange)
C_ORACLE = '#009E73' # oracle              (green)
C_OURS = '#7B3294'   # CA-TOSG / ours      (purple)
C_REF = '#555555'    # references / bounds (grey)
PALETTE = [C_L, C_C16, C_ORACLE, C_OURS, C_C256, C_REF]


def apply():
    matplotlib.rcParams.update({
        # fonts: serif to match an IEEEtran (Times-like) body
        'font.family': 'serif',
        'font.serif': ['STIXGeneral', 'Times New Roman', 'DejaVu Serif'],
        'mathtext.fontset': 'stix',
        'font.size': 8,
        'axes.titlesize': 8.5,
        'axes.labelsize': 8,
        'xtick.labelsize': 7,
        'ytick.labelsize': 7,
        'legend.fontsize': 6.8,
        # lines / axes
        'axes.linewidth': 0.6,
        'lines.linewidth': 1.4,
        'lines.markersize': 4,
        'patch.linewidth': 0.6,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 0.6,
        'ytick.major.width': 0.6,
        'xtick.major.size': 3,
        'ytick.major.size': 3,
        # grid: light, dashed, behind data
        'axes.grid': True,
        'grid.alpha': 0.35,
        'grid.linewidth': 0.4,
        'grid.linestyle': '--',
        'axes.axisbelow': True,
        # spines: drop top/right for a cleaner look
        'axes.spines.top': False,
        'axes.spines.right': False,
        # legend
        'legend.frameon': True,
        'legend.framealpha': 0.9,
        'legend.edgecolor': '0.7',
        'legend.handlelength': 1.8,
        'legend.borderpad': 0.4,
        # colour cycle
        'axes.prop_cycle': matplotlib.cycler(color=PALETTE),
        # output
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.02,
        'pdf.fonttype': 42,   # editable/embeddable text in the PDF
        'ps.fonttype': 42,
    })
