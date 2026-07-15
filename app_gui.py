"""Совместимый вход для plan_generator и старых импортов."""

from gui.app import App

__all__ = ["App"]

if __name__ == "__main__":
    app = App()
    app.mainloop()
