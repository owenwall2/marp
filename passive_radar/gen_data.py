import numpy as np

fs = 8e6
N = 1024
step = 1024
num_blocks = 64
delay_samples = 512


num_samples = num_blocks * step + (N - step)
ref = np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
noise = 0.01 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
surv = np.zeros_like(ref)
surv[delay_samples:] = ref[:-delay_samples]

for i in range(10):
    temp = np.zeros_like(ref)
    temp[delay_samples - i:] = ref[:-(delay_samples - i)]

    surv = surv + temp
# surv[delay_samples:] = ref[:-delay_samples]
    surv = surv + noise

ref.astype(np.complex64).tofile("data/ref")
surv.astype(np.complex64).tofile("data/surv")
print("Synthetic data written")