import numpy as np
import matplotlib.pyplot as plt

ref = np.fromfile("data/ref", dtype=np.complex64)
surv = np.fromfile("data/surv", dtype=np.complex64)

fs = 8e6
c = 299792458.0

N = 1024
step = 1024
num_blocks = 64

lags = np.arange(-(N - 1), N)
path_diff_m = c * lags / fs
pos = path_diff_m >= 0
path_diff_m_pos = path_diff_m[pos]

nfft_delay = 2 * N - 1

num_maps = int(np.floor(min(len(ref), len(surv)) / (num_blocks * step + (N - step))))
print("Number of Plots:", num_maps)

maps = np.zeros((num_maps, num_blocks, nfft_delay), dtype=np.float32)
corr_matrix = np.zeros((num_blocks, nfft_delay), dtype=np.complex64)

for j in range(num_maps):
    map_ref = ref[j * num_blocks * step + (N - step):(j + 1) * num_blocks * step + (N - step)]
    map_surv = surv[j * num_blocks * step + (N - step):(j + 1) * num_blocks * step + (N - step)]

    for i in range(num_blocks):
        start = i * step
        stop = start + N

        block_ref = map_ref[start:stop]
        block_surv = map_surv[start:stop]

        X = np.fft.fft(block_ref, nfft_delay)
        Y = np.fft.fft(block_surv, nfft_delay)
        corr = np.fft.ifft(Y * np.conj(X))
        corr = np.fft.fftshift(corr)

        corr_matrix[i, :] = corr

    doppler_map = np.fft.fftshift(np.fft.fft(corr_matrix, axis=0), axes=0)
    maps[j, :, :] = 20 * np.log10(np.abs(doppler_map) + 1e-12)
    
# only positive range values
maps_pos = maps[:, :, pos]

color_min = np.min(maps_pos)
color_max = np.max(maps_pos)

for k in range(num_maps):
    plt.clf()
    plt.imshow(
        maps_pos[k].T,
        aspect='auto',
        origin='lower',
        interpolation='nearest',
        extent=[-num_blocks // 2, num_blocks // 2 - 1, path_diff_m_pos[0], path_diff_m_pos[-1]],
        vmin=color_min,
        vmax=color_max,
    )
    plt.colorbar(label='Magnitude (dB)')
    plt.xlabel('Doppler bin')
    plt.ylabel('Bistatic Path Difference (m)')
    plt.title('Delay-Doppler Heat Map')
    plt.pause(0.5)

plt.show()
