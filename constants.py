from balls_detection.extract_color_methods import ExtractColorMethod

# beach - space - deluxe3
GAME_VERSION = "deluxe3"

# رقم الشاشة تاكدو انو دائما واحد لان انا يمكن اقلبو تنين مشان اشتغل عالشاشة التانية
MONITOR = 1


""" 
extract_color_method طريقة استخراج اللون - حاليا كلهن بيعتمدو عالمتوسط لهيك بالاخير فينا نشيلن
hc_config بارامترات لتتبع الكرات  وعم اخد نوعين اما ابعاد كبيرة او صغيرة لان بتفرق بالدقة وبعتبة كاني
"""
Deluxe3 = {
    "extract_color_method": ExtractColorMethod.MEAN,
    "hue_sat": {
        "Purple": (143, 133),
        "Blue": (118, 134),
        "Yellow": (24, 125),
        "Green": (52, 139),
        "Red": (175, 134),
    },
    "hc_config": {
        "LARGE": {
            "REFERENCE_WIDTH": 1000,
            "params": {
                "minDist": 13,
                "minRadius": 13,
                "maxRadius": 26,
                "param1": 66,
                "param2": 42,
            },
        },
        "SMALL": {
            "REFERENCE_WIDTH": 730,
            "params": {
                "minDist": 8,
                "minRadius": 5,
                "maxRadius": 17,
                "param1": 39,
                "param2": 25,
            },
        },
    },
}

Space = {
    "extract_color_method": ExtractColorMethod.MEAN,
    "hue_sat": {
        "Red": (1, 190),
        "Cyan": (102, 150),
        "Yellow": (25, 174),
        "Green": (68, 174),
        "Pink": (163, 102),
        "orange": (13, 241),
        "Purple": (139, 175),
    },
    "hc_config": {
        "LARGE": {
            "REFERENCE_WIDTH": 1000,
            "params": {
                "minDist": 11,
                "minRadius": 10,
                "maxRadius": 27,
                "param1": 27,
                "param2": 30,
            },
        },
        "SMALL": {
            "REFERENCE_WIDTH": 730,
            "params": {
                "minDist": 12,
                "minRadius": 9,
                "maxRadius": 19,
                "param1": 32,
                "param2": 24,
            },
        },
    },
}

Beach = {
    "extract_color_method": ExtractColorMethod.MEAN,
    "hue_sat": {
        "Green": (55, 210),
        "Orange": (9, 251),
        "Pink": (160, 222),
        "Blue": (105, 235),
        "Yellow": (25, 240),
        "Cyan": (99, 162),
    },
    "hc_config": {
        "LARGE": {
            "REFERENCE_WIDTH": 1000,
            "params": {
                "minDist": 37,
                "minRadius": 11,
                "maxRadius": 25,
                "param1": 49,
                "param2": 21,
            },
        },
        "SMALL": {
            "REFERENCE_WIDTH": 730,
            "params": {
                "minDist": 13,
                "minRadius": 12,
                "maxRadius": 19,
                "param1": 19,
                "param2": 20,
            },
        },
    },
}
