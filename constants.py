# beach - space - deluxe3
from balls_detection.extract_color_methods import ExtractColorMethod


GAME_VERSION = "beach"

# رقم الشاشة تاكدو انو دائما واحد لان انا يمكن اقلبو تنين مشان اشتغل عالشاشة التانية
MONITOR = 1

""" 
extract_color_method طريقة استخراج اللون - حاليا كلهن بيعتمدو عالمتوسط لهيك بالاخير فينا نشيلن
hc_config بارامترات لتتبع الكرات  وعم اخد نوعين اما ابعاد كبيرة او صغيرة لان بتفرق بالدقة وبعتبة كاني


"""
Deluxe3 = {
    "extract_color_method": ExtractColorMethod.MEAN,
    "assets": {
        "ball_0.png": "Purple",
        "ball_1.png": "Blue",
        "ball_2.png": "Yellow",
        "ball_3.png": "Green",
        "ball_4.png": "Red",
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
                "minDist": 9,
                "minRadius": 5,
                "maxRadius": 20,
                "param1": 42,
                "param2": 28,
            },
        },
    },
}

Beach = {
    "extract_color_method": ExtractColorMethod.MEAN,
    "assets": {
        "ball_0.png": "Green",
        "ball_1.png": "Orange",
        "ball_2.png": "Pink",
        "ball_3.png": "Blue",
        "ball_4.png": "Yellow",
        "ball_5.png": "Cyan",
    },
    "hc_config": {
        "LARGE": {
            "REFERENCE_WIDTH": 1000,
            "params": {
                "minDist": 19,
                "minRadius": 11,
                "maxRadius": 36,
                "param1": 84,
                "param2": 30,
            },
        },
        "SMALL": {
            "REFERENCE_WIDTH": 730,
            "params": {
                "minDist": 18,
                "minRadius": 9,
                "maxRadius": 28,
                "param1": 62,
                "param2": 26,
            },
        },
    },
}

Space = {
    "extract_color_method": ExtractColorMethod.MEAN,
    "assets": {
        "ball_0.png": "Red",
        "ball_1.png": "Cyan",
        "ball_2.png": "Yellow",
        "ball_3.png": "Green",
        "ball_4.png": "Pink",
        "ball_5.png": "orange",
        "ball_6.png": "Purple",
    },
    "hc_config": {
        "LARGE": {
            "REFERENCE_WIDTH": 1000,
            "params": {
                "minDist": 7,
                "minRadius": 10,
                "maxRadius": 27,
                "param1": 71,
                "param2": 33,
            },
        },
        "SMALL": {
            "REFERENCE_WIDTH": 730,
            "params": {
                "minDist": 9,
                "minRadius": 7,
                "maxRadius": 22,
                "param1": 57,
                "param2": 26,
            },
        },
    },
}
