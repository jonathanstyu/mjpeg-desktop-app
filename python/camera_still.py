import cv2 as cv2
import sys

videoURL = sys.argv[1]
cap = cv2.VideoCapture(videoURL)
result, frame = cap.read()
if result: 
  print("NICE")
  cv2.imwrite("../frame.png", frame)
else: 
  print("Fail")