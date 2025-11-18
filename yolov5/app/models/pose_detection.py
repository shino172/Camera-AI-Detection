import numpy as np
import time

# Pose detection configuration
YOLO_TO_MP = {
    0:0,1:2,2:5,3:7,4:8,5:11,6:12,7:13,8:14,
    9:15,10:16,11:23,12:24,13:25,14:26,15:27,16:28
}

HAND_TO_MOUTH_DIST = 30

def kpt2vec(k, w, h):
    """Convert keypoints to vector"""
    vec = [0.0]*99
    for yi, mi in YOLO_TO_MP.items():
        if yi < len(k):
            x,y = k[yi][:2]
            vec[mi*3] = x / w
            vec[mi*3 + 1] = y / h
    return np.array(vec, np.float32)

def check_hand_to_mouth(kpts):
    """Check if hand is near mouth (smoking detection)"""
    if kpts is None or len(kpts) < 11: 
        return False
    nose = kpts[0]; lw, rw = kpts[9], kpts[10]
    dist = lambda a,b: np.linalg.norm(a[:2]-b[:2])
    try:
        if (lw[0] or lw[1]) and dist(nose,lw) < HAND_TO_MOUTH_DIST: 
            return True
        if (rw[0] or rw[1]) and dist(nose,rw) < HAND_TO_MOUTH_DIST: 
            return True
    except:
        return False
    return False

def calc_iou(boxA, boxB):
    """Calculate Intersection over Union"""
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    if interArea <= 0: 
        return 0.0
    boxAArea = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    boxBArea = (boxB[2]-boxB[0]) * (boxB[3]-boxB[1])
    return interArea / float(boxAArea + boxBArea - interArea + 1e-9)