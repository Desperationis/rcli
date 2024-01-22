
class brect:
    """Specify bounding box in absolute curse coordinates."""

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def bottom(self) -> int:
        """Return the y coordinate of the last line"""
        return self.y + self.h - 1

    def right(self) -> int:
        """Return the x coordinate of the rightmost part of the line"""
        return self.x + self.w - 1







