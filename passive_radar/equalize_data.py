import numpy as np

reference = np.load("data/demo_data/reference/passive_radar_maps.npz")
ref_maps_pos = reference["maps_pos"]
ref_path_diff_m_pos = reference["path_diff_m_pos"]
ref_num_blocks = int(reference["num_blocks"])

data = np.load("passive_radar_maps.npz")
maps_pos = data["maps_pos"]
path_diff_m_pos = data["path_diff_m_pos"]
num_blocks = int(data["num_blocks"])

if ref_maps_pos.shape[1:] != maps_pos.shape[1:]:
    raise ValueError("Reference and data map shapes do not match.")

if not np.allclose(ref_path_diff_m_pos, path_diff_m_pos):
    raise ValueError("Range axes do not match.")

if ref_num_blocks != num_blocks:
    raise ValueError("num_blocks does not match.")

# Average each pixel across ALL reference maps
ref_avg = np.mean(ref_maps_pos, axis=0)   # shape: (doppler_bins, range_bins)

# Subtract that reference average from EVERY data map, pixel by pixel
equalized_maps = maps_pos - ref_avg       # shape stays: (num_maps, doppler_bins, range_bins)

np.savez(
    "equalized_passive_radar_maps.npz",
    maps_pos=equalized_maps,
    path_diff_m_pos=path_diff_m_pos,
    num_blocks=num_blocks,
    ref_avg=ref_avg,
)

print("Saved equalized_passive_radar_maps.npz")