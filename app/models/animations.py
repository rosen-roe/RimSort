import traceback
from typing import Callable

from loguru import logger
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class AnimationLabel(QLabel):
    """
    Subclass for QLabel. Displays fading text on the bottom
    status panel.
    """

    def __init__(self) -> None:
        """
        Prepare the QLabel to have its opacity
        changed through a timed animation.
        """
        super(AnimationLabel, self).__init__()
        self.effect = QGraphicsOpacityEffect()
        self.effect.setOpacity(0)
        self.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b"opacity")
        self.timer = QTimer(interval=1000, singleShot=True)
        self.timer.timeout.connect(self.fade)

    def fade(self) -> None:
        """
        Start an animation for fading out the text.
        """
        self.animation.stop()
        self.animation.setDuration(300)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.Linear)
        self.animation.start()

    def start_pause_fade(self, text: str) -> None:
        """
        Start the timer for calling the fade animation.
        The text should be displayed normally for 5 seconds,
        after which the fade animation is called.

        :param text: the string to display and fade
        """
        self.clear()
        if self.timer.isActive:
            self.timer.stop()
            self.animation.stop()
        self.setText(text)
        self.effect.setOpacity(1)
        self.setGraphicsEffect(self.effect)
        self.timer.start(5000)


class LoadingAnimation(QWidget):
    finished = Signal()

    def __init__(self, gif_path: str, target: Callable):
        super().__init__()
        logger.debug("初始化加载动画")
        # Store data
        self.animation_finished = False
        self.data = {}
        # Setup thread
        self.gif_path = gif_path
        self.thread = WorkThread(parent=self, target=target)
        self.thread.data_ready.connect(self.handle_data)
        self.thread.finished.connect(self.prepare_stop_animation)
        self.thread.start()
        # Window properties
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Label and layout
        self.layout = QVBoxLayout(self)
        self.movie = QMovie(self.gif_path)
        self.movie.frameChanged.connect(self.check_animation_stop)
        self.movie.start()
        self.label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.label.setMovie(self.movie)
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        logger.debug("完成加载动画初始化")

    def check_animation_stop(self, frameNumber: int):
        if self.animation_finished and frameNumber == self.movie.frameCount() - 1:
            logger.debug("动画完成")
            self.stop_animation()

    def handle_data(self, data):
        if data:
            logger.debug(f"从线程接收 {type(data)} ")
            self.data = data

    def prepare_stop_animation(self):
        # Set flag when thread finished
        logger.debug("标记要完成的动画")
        self.animation_finished = True

    def stop_animation(self):
        logger.debug("停止动画")
        # Stop animation
        self.label.clear()
        self.movie.stop()
        self.finished.emit()
        self.close()


class WorkThread(QThread):
    data_ready = Signal(object)

    def __init__(self, target: Callable, parent=None):
        QThread.__init__(self)
        self.data = None
        self.target = target

    def run(self):
        try:
            self.data = self.target()
        except Exception as e:
            logger.error(f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
        logger.debug("工作线程已完成，返回到主线程")
        self.data_ready.emit(self.data)
