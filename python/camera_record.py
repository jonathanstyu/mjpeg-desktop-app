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
clip_seconds = 5
if len(sys.argv) > 2:
  try:
    clip_seconds = int(sys.argv[2])
  except ValueError:
    clip_seconds = 5

if clip_seconds <= 0:
  clip_seconds = 5

cap = cv2.VideoCapture(videoURL)
num_frames = 30

# Start calculating the frame dimensions
# start = time.time()

# for i in range(0, num_frames):
#   ret, frame = cap.read()
    
# # Start time 
# end = time.time()

# dimensions = int((num_frames/(end - start)) * 2)
fourcc = cv2.VideoWriter_fourcc(*'MP4V')
writer = cv2.VideoWriter('../output--{0}.mp4'.format(time.strftime('%y-%m-%d-%H-%M')), fourcc, 5.0, (640, 480))

start_time = time.time()
while time.time() < start_time + clip_seconds:
  try:
    result, frame = cap.read()
    if result:
      writer.write(frame)
  except Exception as e: 
    print(e)

cap.release()
writer.release()

print("Success")
