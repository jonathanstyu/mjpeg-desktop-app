import sys
import time
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir in sys.path:
  sys.path.remove(script_dir)

try:
  import cv2 as cv2
except ModuleNotFoundError as error:
  if 'cv2' in str(error):
    print("ERROR: OpenCV dependency missing. Install with: python3 -m pip install opencv-python")
    sys.exit(1)
  raise

videoURL = sys.argv[1]
cap = cv2.VideoCapture(videoURL)
result, frame = cap.read()
if result: 
  print("NICE")
  cv2.imwrite("../frame--{0}.png".format(time.strftime('%y-%m-%d-%H-%M')), frame)
else: 
  print("Fail")
