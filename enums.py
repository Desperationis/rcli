class CHOICE:
    NONE = 0b0000000
    BACK = 0b0000001
    SELECTED = 0b0000010
    DOWNLOAD = 0b0000100
    REFRESH = 0b0001000


class SelectedOption:
    def __init__(self, choice=CHOICE.NONE, data=None):
        self.choice = choice
        self.data = data


class SCENES:
    CHOOSE_FILE = 0b0001
    FUZZY_SEARCH = 0b0010
    DOWNLOAD = 0b0100
    REFRESH_DATABASE = 0b1000
