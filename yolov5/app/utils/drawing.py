import cv2

def draw_label_with_bg(img, text, org, color=(0,0,255), font=cv2.FONT_HERSHEY_SIMPLEX, 
                      scale=0.8, thickness=2, pad=6):
    """Draw text with background for better visibility"""
    (tw, th), bl = cv2.getTextSize(text, font, scale, thickness)
    x, y = org
    bg_tl = (x - pad, y - th - pad)
    bg_br = (x + tw + pad, y + bl + pad)
    cv2.rectangle(img, bg_tl, bg_br, (0,0,0), -1)
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)