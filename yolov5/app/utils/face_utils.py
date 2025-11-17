import face_recognition, numpy as np


def recognize_faces(frame, known_encodings, known_names, tolerance=0.45):
    rgb = frame[:, :, ::-1]
    locs = face_recognition.face_locations(rgb)
    encs = face_recognition.face_encodings(rgb, locs)


    results = []
    for loc, enc in zip(locs, encs):
        dists = [np.linalg.norm(enc - k) for k in known_encodings]
        if dists:
            idx = int(np.argmin(dists))
            if dists[idx] < tolerance:
                results.append({"loc": loc, "name": known_names[idx]})
    return results