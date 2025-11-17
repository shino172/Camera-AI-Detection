import cv2


def draw_label_with_bg(img, text, org, color=(0,0,255)):
    (tw, th), bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    x, y = org
    cv2.rectangle(img, (x, y - th - 6), (x + tw + 6, y + 6), (0, 0, 0), -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)