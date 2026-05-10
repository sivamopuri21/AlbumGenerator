import logging
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger(__name__)

_face_app = None


def _load_model():
    global _face_app
    if _face_app is None:
        try:
            from insightface.app import FaceAnalysis
            _face_app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"],
            )
            _face_app.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("InsightFace model loaded.")
        except Exception as e:
            logger.warning("InsightFace unavailable, using OpenCV fallback: %s", e)
            _face_app = "opencv_fallback"


def detect_faces_insightface(image_path: Path) -> int:
    _load_model()
    img = cv2.imread(str(image_path))
    if img is None:
        logger.warning("Could not read image for face detection: %s", image_path.name)
        return 0
    if _face_app == "opencv_fallback":
        count = _detect_faces_opencv(img)
        logger.debug("Face detection (OpenCV) %s: %d faces", image_path.name, count)
        return count
    try:
        faces = _face_app.get(img)
        logger.debug("Face detection (InsightFace) %s: %d faces", image_path.name, len(faces))
        return len(faces)
    except Exception as e:
        logger.warning("InsightFace failed for %s, falling back to OpenCV: %s", image_path.name, e)
        count = _detect_faces_opencv(img)
        logger.debug("Face detection (OpenCV fallback) %s: %d faces", image_path.name, count)
        return count


def _detect_faces_opencv(img: np.ndarray) -> int:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    return len(faces)
