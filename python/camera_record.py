import cv2 as cv2
import sys
import time

videoURL = sys.argv[1]
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
while time.time() < start_time + 5:
  try:
    result, frame = cap.read()
    writer.write(frame)
  except Exception as e: 
    print(e)

cap.release()

print("Success")