# Render Time Estimator + Logger

[![Blender 4.2+](https://img.shields.io/badge/Blender-4.2%2B%20LTS-orange.svg)](https://www.blender.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Category: Render](https://img.shields.io/badge/Category-Render-green.svg)](https://novastrikes.com/)
[![Support Creator](https://img.shields.io/badge/Support-Gumroad%20Coffee-ff69b4.svg)](https://novastrikes.gumroad.com/coffee)

Predict render times before you commit, track live ETAs during rendering, and maintain a local history log of past render performance in Blender 4.2+ LTS.

---

## 🚀 Key Features

- **⏱️ Pre-Render Time Estimation**: Predict render times before committing hours to a full render pass.
- **📈 Two-Point Linear Regression Model**: Accurately isolates fixed setup overhead (BVH build, denoiser initialization, GPU kernel dispatch) from scaling work, preventing false 10x+ overestimations on fast or simple scenes.
- **🎯 Adaptive Sampling Awareness**: Detects Cycles `use_adaptive_sampling` and noise thresholds, automatically using resolution-based test passes to preserve early-out pixel stopping.
- **📊 Per-Frame & Animation Breakdown**: Displays both single-frame duration and total animation time ($N \text{ frames}$) explicitly in the UI.
- **⏳ Live ETA Tracking**: Real-time progress monitoring during active renders (`F12` / `Ctrl+F12`) using a rolling average of actual measured frame times.
- **📜 Render History & CSV Export**: Automatically logs completed and cancelled renders locally with technical metadata (resolution, samples, engine, duration) and one-click CSV export.
- **🔒 100% Free & Open Source**: No activation keys, no feature gating, and no internet connection required.

---

## ⚠️ Important Cautions & Limitations

While the pre-render estimator provides a reliable mathematical approximation, users should be aware of the following technical behaviors:

1. **Brief UI Pause During Estimation**:
   - The estimator runs two rapid background test passes (20% and 40% resolution/samples) to compute the two-point regression curve.
   - Blender's UI will pause briefly while these test frames calculate. A confirmation dialog will prompt you before running.
2. **Frame-to-Frame Scene Complexity Variance**:
   - Estimation measures the active frame. If later frames in an animation add massive geometry, complex fluid/smoke simulations, or heavy particle bursts, actual frame times will naturally increase.
3. **GPU VRAM & System RAM Swapping**:
   - Low-resolution test passes require less VRAM. If full-resolution rendering exceeds your GPU's VRAM and triggers system RAM swapping, full render times will be significantly slower than estimated.
4. **First-Render GPU Kernel Compilation**:
   - The first render pass after opening Blender often includes GPU shader compilation overhead. Subsequent renders in the same session will be faster.

---

## 📦 Installation

### Option 1: Blender Extension (Blender 4.2+)
1. Download `render_time_estimator_extension.zip` from the latest release.
2. In Blender, go to **Edit > Preferences > Get Extensions**.
3. Click the top-right menu icon (⚙️) and select **Install from Disk...**
4. Select `render_time_estimator_extension.zip`.

### Option 2: Classic Addon Format
1. Download `render_time_estimator.zip`.
2. In Blender, go to **Edit > Preferences > Add-ons**.
3. Click the top-right menu icon (⚙️) and select **Install from Disk...**
4. Enable **Render Time Estimator + Logger**.

---

## 📖 How to Use

1. Open the **Render Properties** tab in Blender.
2. Scroll down to the **Render Insights** panel.
3. Click **Estimate Render Time** to run a pre-render calculation pass.
4. Start your render (`F12` for still frame, `Ctrl+F12` for animation).
5. Watch real-time elapsed time and calculated completion ETA under **Live ETA Tracking**.
6. View past render durations, settings, and export reports under **Render History**.

---

## 👤 Maintainer & Credits

Created and maintained by **NovaStrikes (Hamayl Shahbaz)**.

- 🌐 Portfolio: [novastrikes.com](https://novastrikes.com/)
- 💻 GitHub: [@NvxStrikes](https://github.com/NvxStrikes)
- ✉️ Contact: [contact@novastrikes.com](mailto:contact@novastrikes.com)
- ☕ Support the Creator: [Gumroad Coffee](https://novastrikes.gumroad.com/coffee)

---

## 📜 License

Distributed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See `LICENSE` for details.
