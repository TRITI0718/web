def hex_to_rgb(hex_color):
    """
    十六进制颜色转 RGB
    例如：
    #FF0000 -> (255, 0, 0)
    """
    hex_color = hex_color.lstrip("#")

    return tuple(
        int(hex_color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def rgb_to_hex(rgb):
    """
    RGB 转十六进制颜色
    """
    return "#{:02X}{:02X}{:02X}".format(
        int(rgb[0]),
        int(rgb[1]),
        int(rgb[2])
    )


def interpolate_color(color1, color2, factor):
    """
    在两个颜色之间进行线性插值

    factor:
    0 -> color1
    1 -> color2
    """

    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    rgb = tuple(
        rgb1[i] + (rgb2[i] - rgb1[i]) * factor
        for i in range(3)
    )

    # 保留小数精度，避免相邻热量值在取整为 HEX 时
    # 偶然落到同一个颜色。
    return "rgb({:.3f} {:.3f} {:.3f})".format(
        rgb[0],
        rgb[1],
        rgb[2],
    )


def get_calorie_color(calories, max_calories):
    """
    将数值按 0 到最大值线性归一化，并在相邻色标间
    进行分段线性插值。相同数值始终得到相同颜色。
    """

    if max_calories <= 0:
        return "#9EDCF5"

    ratio = min(
        max(float(calories) / float(max_calories), 0.0),
        1.0,
    )

    color_stops = [
        "#9EDCF5",  # 浅蓝
        "#43A047",  # 绿
        "#9CCC65",  # 黄绿
        "#F4D03F",  # 黄
        "#F39C12",  # 橙
        "#E74C3C",  # 红
        "#8B1E1E",  # 深红
    ]

    segment_count = len(color_stops) - 1
    scaled_position = ratio * segment_count
    segment_index = min(
        int(scaled_position),
        segment_count - 1,
    )
    segment_factor = scaled_position - segment_index

    return interpolate_color(
        color_stops[segment_index],
        color_stops[segment_index + 1],
        segment_factor,
    )
