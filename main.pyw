from gui import App
from logger import setup_logger

if __name__ == "__main__":
    logger = setup_logger()
    app = App(logger)
    app.mainloop()