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

    return rgb_to_hex(rgb)


def get_calorie_color(calories, max_calories):
    """
    根据热量生成连续渐变颜色。

    0 kcal   -> 浅蓝
    低热量   -> 绿色
    中低热量 -> 黄色
    中热量   -> 橙色
    高热量   -> 红色
    最高热量 -> 深红
    """

    if calories <= 0:
        return "#9EDCF5"

    if max_calories <= 0:
        return "#9EDCF5"

    ratio = calories / max_calories

    ratio = min(max(ratio, 0), 1)

    # 0% - 20%
    # 绿色 -> 黄绿色
    if ratio <= 0.20:

        factor = ratio / 0.20

        return interpolate_color(
            "#43A047",
            "#9CCC65",
            factor
        )

    # 20% - 40%
    # 黄绿色 -> 黄色
    elif ratio <= 0.40:

        factor = (
            ratio - 0.20
        ) / 0.20

        return interpolate_color(
            "#9CCC65",
            "#F4D03F",
            factor
        )

    # 40% - 60%
    # 黄色 -> 橙色
    elif ratio <= 0.60:

        factor = (
            ratio - 0.40
        ) / 0.20

        return interpolate_color(
            "#F4D03F",
            "#F39C12",
            factor
        )

    # 60% - 80%
    # 橙色 -> 红色
    elif ratio <= 0.80:

        factor = (
            ratio - 0.60
        ) / 0.20

        return interpolate_color(
            "#F39C12",
            "#E74C3C",
            factor
        )

    # 80% - 100%
    # 红色 -> 深红
    else:

        factor = (
            ratio - 0.80
        ) / 0.20

        return interpolate_color(
            "#E74C3C",
            "#8B1E1E",
            factor
        )