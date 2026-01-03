class GameRegion:
    def __init__(self, x, y, w, h, original_image):
        self.x = int(x)         # الإحداثيات يجب أن تكون int
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.center_x = self.x + (self.w // 2)
        self.center_y = self.y + (self.h // 2)
        # الصورة المقصوصة (ROI) الأولية
        if original_image is not None:
            self.roi = original_image[y:y+h, x:x+w]
        else:
            self.roi = None

    def update_roi(self, new_frame):
        """تحديث صورة الـ ROI في كل إطار جديد من الفيديو"""
        # هنا نفترض أن new_frame هو الصورة المقصوصة بالفعل
        self.roi = new_frame

    def to_global(self, local_x, local_y):
        return (self.x + local_x, self.y + local_y)

    def __str__(self):
        return f"GameRegion(x={self.x}, y={self.y}, w={self.w}, h={self.h})"
    
    