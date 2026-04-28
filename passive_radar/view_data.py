import numpy as np
import matplotlib.pyplot as plt

# data = np.load("passive_radar_maps.npz")
data = np.load("equalized_passive_radar_maps.npz")


maps_pos = data["maps_pos"]
path_diff_m_pos = data["path_diff_m_pos"]
num_blocks = int(data["num_blocks"])


fs = 12e6
step = 128

time_per_map = num_blocks * step / fs

total_time = maps_pos.shape[0] * time_per_map

print("Total Time", total_time)


threshold = 20
gain = 100

for k in range(int(8000),maps_pos.shape[0], 20):
    plt.clf()

    frame = maps_pos[k].T.copy()

    mask = frame > threshold
    frame[mask] = threshold + gain * (frame[mask] - threshold)


    plt.imshow(
        frame,
        aspect="auto",
        origin="lower",
        interpolation="nearest",
        extent=[
            -num_blocks // 2,
            num_blocks // 2 - 1,
            path_diff_m_pos[0],
            path_diff_m_pos[-1],
        ],
        vmin = -40,
        vmax = 60
    )
    plt.colorbar(label="Magnitude (dB)")
    plt.xlabel("Doppler bin")
    plt.ylabel("Bistatic Path Difference (m)")
    plt.title(f"Delay-Doppler Heat Map {k}  |  t = {k * time_per_map:.6f} s")
    plt.pause(0.01)

    # peak = np.max(maps_pos[k])
    # if peak > 0:
    #     idx = np.unravel_index(np.argmax(maps_pos[k]), maps_pos[k].shape)
    #     doppler_inx, range_idx = idx

    #     range_m = path_diff_m_pos[range_idx]
    #     if range_m > 150:
    #         print(f"Map {k}: Time {k * time_per_map:.6f}s peak {peak:.2f} dB at Doppler bin {doppler_inx}, range {int(range_m)}")
 
plt.show()

# Best result: Plane N128, Start map 28000