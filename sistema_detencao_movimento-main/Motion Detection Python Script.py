"""
Sistema Inteligente de Deteccao de Movimento
Autor: Luiz Henrique
Inspirado no projeto de Antonio (sistema_detencao_movimento).

Recursos:
- Deteccao de ROSTOS e MAOS em tempo real (MediaPipe)
- Identificacao de OBJETOS (YOLOv8)
- Data e hora no video
- Alarme por movimento, com foto automatica do evento
- Modo inteligente: so dispara se houver movimento E uma pessoa na cena
- CONTROLE POR GESTOS (mao voltada para a camera, dedos para cima):
    * Mao aberta por 2s ........ LIGA o alarme
    * Paz (V) por 1s ........... tira foto com contagem 3-2-1
    * Senha gestual ............ DESLIGA o alarme (sequencia secreta)

Teclas:
  A = liga/desliga o alarme    P = modo inteligente
  S = foto manual              F = sair
"""

import os
import sys
import threading
import time
from datetime import datetime

import cv2
import imutils
import mediapipe as mp
import numpy as np
from ultralytics import YOLO

# ----------------------------- CONFIGURACOES -----------------------------
CAMERA_INDEX = 0
FRAME_WIDTH = 640
MIN_AREA = 800
THRESHOLD = 25
ALARM_TRIGGER = 20
BLUR = (21, 21)

YOLO_MODEL = "yolov8n.pt"
YOLO_CONF = 0.5
YOLO_EVERY_N_FRAMES = 3

# Gestos disponiveis: "OPEN" (mao aberta), "FIST" (punho),
# "PEACE" (indicador + medio), "ONE" (so o indicador)
ARM_HOLD = 2.0            # segundos com a mao aberta para ligar o alarme
PHOTO_HOLD = 1.0          # segundos com o gesto de paz para iniciar a foto
COUNTDOWN = 3             # contagem regressiva da foto (segundos)
SECRET_SEQUENCE = ["FIST", "PEACE", "OPEN"]   # TROQUE PELA SUA SENHA!
SEQ_HOLD = 0.8            # segundos segurando cada gesto da senha
SEQ_TIMEOUT = 8.0         # tempo maximo entre gestos da senha

SAVE_DIR = "capturas"
# -------------------------------------------------------------------------

os.makedirs(SAVE_DIR, exist_ok=True)

# Observacao: o OpenCV nao desenha acentos com cv2.putText,
# por isso os textos na tela estao sem acento.

GESTURE_LABELS = {
    "OPEN": "MAO ABERTA",
    "FIST": "PUNHO",
    "PEACE": "PAZ",
    "ONE": "INDICADOR",
}


def open_camera():
    if sys.platform == "win32":
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return cap


def prepare(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, BLUR, 0)


def play_beep():
    if sys.platform == "win32":
        import winsound
        winsound.Beep(2500, 1000)
    else:
        print("\a", end="", flush=True)
        time.sleep(1)


def now_text():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def save_snapshot(frame, prefix="foto"):
    name = datetime.now().strftime(f"{prefix}_%Y%m%d_%H%M%S.jpg")
    path = os.path.join(SAVE_DIR, name)
    cv2.imwrite(path, frame)
    print(f"Foto salva: {path}")


def put_label(frame, text, x, y, color):
    """Texto com fundo escuro para ficar legivel em qualquer imagem."""
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = max(y, th + 6)
    cv2.rectangle(frame, (x, y - th - 6), (x + tw + 4, y + 2), (0, 0, 0), -1)
    cv2.putText(frame, text, (x + 2, y - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def draw_progress(frame, ratio, label):
    bar_w = 200
    x, y = frame.shape[1] - bar_w - 10, 10
    cv2.rectangle(frame, (x, y), (x + bar_w, y + 14), (60, 60, 60), -1)
    cv2.rectangle(frame, (x, y), (x + int(bar_w * min(ratio, 1.0)), y + 14),
                  (0, 255, 255), -1)
    put_label(frame, label, x, y + 34, (0, 255, 255))


# ------------------------------ DETECTORES -------------------------------
mp_face = mp.solutions.face_detection
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

face_detector = mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.6)
hands_detector = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.6,
                                min_tracking_confidence=0.5)
yolo = YOLO(YOLO_MODEL)


def detect_faces(frame, rgb):
    h, w = frame.shape[:2]
    boxes = []
    result = face_detector.process(rgb)
    if result.detections:
        for det in result.detections:
            b = det.location_data.relative_bounding_box
            x, y = max(int(b.xmin * w), 0), max(int(b.ymin * h), 0)
            boxes.append((x, y, int(b.width * w), int(b.height * h)))
    return boxes


def detect_hands(frame, rgb):
    h, w = frame.shape[:2]
    hands = []
    result = hands_detector.process(rgb)
    if result.multi_hand_landmarks:
        for lm in result.multi_hand_landmarks:
            xs = [p.x * w for p in lm.landmark]
            ys = [p.y * h for p in lm.landmark]
            box = (int(min(xs)), int(min(ys)),
                   int(max(xs) - min(xs)), int(max(ys) - min(ys)))
            hands.append((lm, box))
    return hands


def detect_objects(frame):
    objects = []
    result = yolo(frame, verbose=False, conf=YOLO_CONF)[0]
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        name = yolo.names[int(box.cls[0])]
        objects.append((name, float(box.conf[0]), (x1, y1, x2, y2)))
    return objects


# ------------------------------- GESTOS ----------------------------------
def classify_gesture(lm):
    """Classifica o gesto pelos 4 dedos (indicador, medio, anelar, minimo).

    Funciona com a mao voltada para a camera e os dedos apontando para cima.
    Um dedo esta 'levantado' se a ponta esta acima da articulacao do meio.
    """
    p = lm.landmark
    tips = (8, 12, 16, 20)
    pips = (6, 10, 14, 18)
    up = tuple(p[t].y < p[k].y for t, k in zip(tips, pips))

    if all(up):
        return "OPEN"
    if not any(up):
        return "FIST"
    if up == (True, True, False, False):
        return "PEACE"
    if up == (True, False, False, False):
        return "ONE"
    return None


class GestureTracker:
    """Estabiliza o gesto (evita piscadas) e mede por quanto tempo ele e mantido."""

    STABLE_FRAMES = 4

    def __init__(self):
        self.gesture = None
        self.since = time.time()
        self.fired = False
        self._candidate = None
        self._count = 0

    def update(self, gesture):
        if gesture == self._candidate:
            self._count += 1
        else:
            self._candidate = gesture
            self._count = 1
        if self._count >= self.STABLE_FRAMES and gesture != self.gesture:
            self.gesture = gesture
            self.since = time.time()
            self.fired = False

    def held(self):
        return 0.0 if self.gesture is None else time.time() - self.since

    def ready(self, needed):
        return self.gesture is not None and not self.fired and self.held() >= needed

    def consume(self):
        self.fired = True


# ------------------------------- ALARME ----------------------------------
alarm = False
alarm_mode = False
smart_mode = True
alarm_counter = 0


def beep_alarm():
    global alarm
    for _ in range(5):
        if not alarm_mode:
            break
        print("ALARME!")
        play_beep()
    alarm = False


# ------------------------------- PRINCIPAL -------------------------------
def main():
    global alarm, alarm_mode, smart_mode, alarm_counter

    cap = open_camera()
    if not cap.isOpened():
        raise SystemExit("Nao foi possivel abrir a camera.")

    ok, frame = cap.read()
    if not ok:
        raise SystemExit("Nao foi possivel ler a imagem da camera.")
    frame = imutils.resize(frame, width=FRAME_WIDTH)
    reference = prepare(frame)

    objects = []
    frame_idx = 0

    tracker = GestureTracker()
    seq_idx = 0              # quantos gestos da senha ja foram acertados
    seq_time = 0.0
    countdown_end = None     # momento em que a foto sera tirada
    flash_until = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = imutils.resize(frame, width=FRAME_WIDTH)
        raw = frame.copy()  # copia limpa (sem desenhos) para fotos e recalibragem
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        now = time.time()

        # --- Rostos, maos e objetos
        faces = detect_faces(frame, rgb)
        hands = detect_hands(frame, rgb)
        if frame_idx % YOLO_EVERY_N_FRAMES == 0:
            objects = detect_objects(frame)
        frame_idx += 1

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            put_label(frame, "Rosto", x, y - 4, (0, 255, 0))

        for lm, (x, y, w, h) in hands:
            mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 200, 0), 2)
            put_label(frame, "Mao", x, y - 4, (255, 200, 0))

        person_in_scene = bool(faces)
        for name, conf, (x1, y1, x2, y2) in objects:
            if name == "person":
                person_in_scene = True
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
            put_label(frame, f"{name} {conf:.0%}", x1, y1 - 4, (0, 165, 255))

        # --- Gestos
        gesture = classify_gesture(hands[0][0]) if hands else None
        tracker.update(gesture)

        if countdown_end is None:
            if not alarm_mode:
                # Alarme desligado: mao aberta liga, paz tira foto
                if tracker.gesture == "OPEN" and tracker.ready(ARM_HOLD):
                    tracker.consume()
                    alarm_mode = True
                    alarm_counter = 0
                    reference = prepare(raw)
                elif tracker.gesture == "PEACE" and tracker.ready(PHOTO_HOLD):
                    tracker.consume()
                    countdown_end = now + COUNTDOWN
            else:
                # Alarme ligado: so a senha gestual desliga
                if seq_idx > 0 and now - seq_time > SEQ_TIMEOUT:
                    seq_idx = 0
                if tracker.ready(SEQ_HOLD):
                    tracker.consume()
                    if tracker.gesture == SECRET_SEQUENCE[seq_idx]:
                        seq_idx += 1
                        seq_time = now
                        if seq_idx == len(SECRET_SEQUENCE):
                            alarm_mode = False
                            alarm_counter = 0
                            seq_idx = 0
                    else:
                        seq_idx = 1 if tracker.gesture == SECRET_SEQUENCE[0] else 0
                        seq_time = now

        # --- Deteccao de movimento (somente com o alarme ligado)
        if alarm_mode:
            gray = prepare(raw)
            diff = cv2.absdiff(reference, gray)
            thresh = cv2.threshold(diff, THRESHOLD, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours = cv2.findContours(
                thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(contours)

            moving = False
            for c in contours:
                if cv2.contourArea(c) < MIN_AREA:
                    continue
                moving = True
                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

            triggered = moving and (person_in_scene or not smart_mode)
            if triggered:
                alarm_counter += 1
            elif alarm_counter > 0:
                alarm_counter -= 1

            reference = cv2.addWeighted(reference, 0.98, gray, 0.02, 0)
            status, color = "ALARME ATIVO", (0, 0, 255)
        else:
            status, color = "ALARME DESLIGADO", (0, 200, 0)

        # --- Disparo do alarme
        if alarm_counter > ALARM_TRIGGER and not alarm:
            alarm = True
            save_snapshot(frame, prefix="alarme")
            threading.Thread(target=beep_alarm, daemon=True).start()

        # --- Contagem regressiva e foto por gesto
        if countdown_end is not None:
            remaining = countdown_end - now
            if remaining <= 0:
                photo = raw.copy()
                put_label(photo, now_text(), 10, photo.shape[0] - 10, (255, 255, 255))
                save_snapshot(photo, prefix="gesto")
                flash_until = now + 0.25
                countdown_end = None
            else:
                number = str(int(remaining) + 1)
                (tw, th), _ = cv2.getTextSize(number, cv2.FONT_HERSHEY_SIMPLEX, 5, 8)
                cx = (frame.shape[1] - tw) // 2
                cy = (frame.shape[0] + th) // 2
                cv2.putText(frame, number, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX,
                            5, (0, 0, 0), 14, cv2.LINE_AA)
                cv2.putText(frame, number, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX,
                            5, (255, 255, 255), 8, cv2.LINE_AA)

        # --- Informacoes na tela
        h_img = frame.shape[0]
        put_label(frame, status, 10, 25, color)

        if tracker.gesture:
            put_label(frame, f"Gesto: {GESTURE_LABELS[tracker.gesture]}",
                      10, 50, (0, 255, 255))

        needed, label = None, ""
        if countdown_end is None and tracker.gesture and not tracker.fired:
            if alarm_mode:
                needed, label = SEQ_HOLD, "Senha"
            elif tracker.gesture == "OPEN":
                needed, label = ARM_HOLD, "Ligando alarme"
            elif tracker.gesture == "PEACE":
                needed, label = PHOTO_HOLD, "Foto"
        if needed:
            draw_progress(frame, tracker.held() / needed, label)

        if alarm_mode:
            dots = "*" * seq_idx + "-" * (len(SECRET_SEQUENCE) - seq_idx)
            put_label(frame, f"Senha gestual: {dots}", 10, 75, (0, 255, 255))

        put_label(frame, now_text(), 10, h_img - 30, (255, 255, 255))
        put_label(
            frame,
            f"Rostos: {len(faces)} | Maos: {len(hands)} | Objetos: {len(objects)} | "
            f"Inteligente: {'ON' if smart_mode else 'OFF'}",
            10, h_img - 10, (255, 255, 255))

        # --- Flash da foto
        if now < flash_until:
            white = np.full_like(frame, 255)
            frame = cv2.addWeighted(frame, 0.3, white, 0.7, 0)

        cv2.imshow("Sistema Inteligente - Luiz Henrique", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("a"):
            alarm_mode = not alarm_mode
            alarm_counter = 0
            seq_idx = 0
            if alarm_mode:
                reference = prepare(raw)
        elif key == ord("p"):
            smart_mode = not smart_mode
        elif key == ord("s"):
            save_snapshot(frame, prefix="manual")
        elif key == ord("f"):
            alarm_mode = False
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()