import cv2 as cv2
import sys
import time

videoURL = sys.argv[1]
cap = cv2.VideoCapture(videoURL)
result, frame = cap.read()
if result: 
  print("NICE")
  cv2.imwrite("../frame--{0}.png".format(time.strftime('%y-%m-%d-%H-%M')), frame)
else: 
  print("Fail")
