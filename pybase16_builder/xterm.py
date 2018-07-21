import colormath.color_objects as cobj
import colormath.color_conversions as cconv
import colormath.color_diff as cdiff
import munkres

def approx_xterm_colors(hex_rgbs):
    """Calculate the approximate unique xterm color for every input color"""
    matrix = rgb_xterm_diff_matrix(hex_rgbs)
    m = munkres.Munkres()
    indexes = m.compute(matrix)

    for _, column in indexes:
        yield column + 16

def rgb_xterm_diff_matrix(hex_rgbs):
    """Return a matrix with the color difference between the input colors and
    xterm colors"""
    return [xterm_diffs(c) for c in hex_rgbs]

def xterm_diffs(hex_rgb):
    """Retrun the color differences between the input color and every xterm
    color"""
    def xterm_objs():
        for xterm_color in xterm_non_system_colors():
            yield cobj.sRGBColor(*xterm_color, is_upscaled=True)

    rgb_obj = cobj.sRGBColor.new_from_rgb_hex(hex_rgb)
    return [color_diff(rgb_obj, x) for x in xterm_objs()]

def xterm_non_system_colors():
    """All xterm colors as (r, g, b) tuple stating from xterm color #16"""
    # colors
    color_vals = [0, 95, 135, 175, 215, 255]
    for r in color_vals:
        for g in color_vals:
            for b in color_vals:
                yield (r, g, b)
    # gray
    for x in range(8, 238+1, 10):
        yield (x, x, x)

def color_diff(c1, c2):
    """Calculate the perceptual color difference of two colors with the CIE2000
    algorithm"""
    color1_lab = cconv.convert_color(c1, cobj.LabColor);
    color2_lab = cconv.convert_color(c2, cobj.LabColor);
    return cdiff.delta_e_cie2000(color1_lab, color2_lab);
