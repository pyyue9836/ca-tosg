# Registered non-result literals in the delivered manuscript

`tests/test_paper_numbers_are_macros.py` requires every numeric literal in `paper/main.tex` and
`paper/supplementary.tex` to be either (a) a macro reference, or (b) covered by one of the patterns
below. **What is locked is that every experimental RESULT comes from a macro or a generated table —
not that LaTeX may contain no digits** (V2-R48 B-1).

Each row is `RX <regex>` followed by an indented reason. The regex is matched against the literal
together with a small window of the text around it, so a pattern can require its own context.

The categories permitted by V2-R48 B-2 are: sectioning and cross-references; protocol definitions
fixed by design rather than measured; standard names; dataset and algorithm names; and registered
protocol constants. Anything else — AP, F1, bounds, savings, payloads, action shares, frame and
scene counts, loss-rate responses, position effects, Where2comm rates, and every derived
"×-fold" / "percentage point" / "order of magnitude" claim — must come from a macro (B-3).

RX \b2\b(?=-bit|~bits? per frame|\s*bits of control)
    the control request width. A protocol definition, fixed by design, not a measurement.
RX \b3\b(?=D\b)
    "3D object detection" — part of a term of art.
RX \b0\.5\b(?=[^0-9]|$)
    the AP IoU threshold in "AP@0.5". A metric definition, not a measured value.
RX \b0\.7\b(?=[^0-9]|$)
    the AP IoU threshold in "AP@0.7". Same.
RX \b1/2\b
    the LDPC code rate. A protocol constant; the block lengths themselves are macros.
RX \b802\.11bd\b
RX \b5G\b
RX \bNR\b
    standard names.
RX \b0\.02\b(?=[^0-9])
    Where2comm's own communication threshold — a control PARAMETER of the external baseline that
    indexes which row of its sweep is quoted, not a result read off that row. Every number read off
    the row (its rate and its APs) is a macro.
RX \b24\b(?=[- ](?:evaluated )?points?\b)
    the size of the external baseline's threshold sweep — a design fact of that sweep. Its cells
    are a generated table.
RX \b9\b(?=-fold\b)
    the LOSO fold count: one fold per development scene, fixed by the split, not measured.
RX \b11\b(?=-point\b)
    the SNR grid size, fixed by the protocol.
RX \b19\b(?=\s+statistics\b)
    how the 23 cue fields divide into perception and channel groups; the schema is frozen and its
    full listing is a generated table.
RX \b0\.999\b
    the RETIRED v1 feasibility threshold, quoted only where the manuscript explains that it was
    retired. Quoting a withdrawn constant in the sentence that withdraws it is correct content.
RX \b1\b(?=\s*=\s*|\s*\)|\s*,)
    unit and index literals inside mathematics.
RX 10\^\{?-?[0-9]
    exponent notation inside mathematics.
RX (?<![\d.])3(?=D detection|D box|D object)
    "3D detection", "3D box", "3D object detection" — terms of art.
RX \b95\b(?=\\?%\s*(?:lower|confidence|CI))
    the confidence level of an interval. A statistical definition fixed in advance, not a result;
    the bound it qualifies is always a macro.
RX \b23\b(?=-dimensional|-d\b|\s+dimensions?\b|\s+fields?\b)
    the cue-vector width stated as a protocol definition. The schema is frozen at this size by
    design; the field listing itself is a generated table.
RX (?<![\d-])\d{4}(?=-\d{2}-\d{2})|(?<=\d{4}-)\d{2}(?=-\d{2}\b)|(?<=\d{4}-\d{2}-)\d{2}\b
    an ISO calendar date. Dates are provenance -- when a value was fixed, and against what it was
    fixed in advance of -- not measurements, and the only one in the delivered text is the
    preregistration date of the non-inferiority margin.
