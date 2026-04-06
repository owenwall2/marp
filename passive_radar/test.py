import numpy as np
import matplotlib.pyplot as plt

ref = np.fromfile("data/ref", dtype=np.complex64)
surv = np.fromfile("data/surv", dtype=np.complex64)

fs = 32e3
c = 299792458.0
N = 1024
step = 1024
num_blocks = 64
nfft_delay = 2 * N - 1

# Process just ONE block manually
block_ref = ref[0:N]
block_surv = surv[0:N]

window = np.hanning(N)
X = np.fft.fft(block_ref * window, nfft_delay)
Y = np.fft.fft(block_surv * window, nfft_delay)
corr = np.fft.ifft(Y * np.conj(X))
corr = np.fft.fftshift(corr)

magnitude = 20 * np.log10(np.abs(corr) + 1e-12)

plt.figure()
plt.plot(magnitude)
plt.title("Single block cross-correlation")
plt.xlabel("Lag index")
plt.ylabel("dB")
plt.show()

# Find the peak
peak = np.argmax(magnitude)
print(f"Peak at lag index: {peak}")
print(f"Center (zero lag) at index: {nfft_delay // 2}")
print(f"Peak offset from center: {peak - nfft_delay // 2} samples")
print(f"Expected offset: +512 samples")