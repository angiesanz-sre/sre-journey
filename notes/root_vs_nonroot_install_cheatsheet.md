# ⚡ Root vs Non-Root Install Cheat Sheet (macOS/Linux)

| Situation / Tool | Root Needed? | Why / Notes |
|------------------|--------------|-------------|
| Homebrew / Conda / NVM / pyenv (package & language managers) | ❌ No | Designed to live in user space. They manage their own folders and permissions. |
| Programming languages (Python, Node, Go, Rust, etc. via Homebrew or manager) | ❌ No | Installed under `/opt/homebrew` or `~/.nvm` etc. Isolated from system. |
| Git, VS Code, CLI utilities (via Homebrew) | ❌ No | Safe, managed in Homebrew’s folder. |
| Python libraries (via pip install --user or inside venv) | ❌ No | User-level install keeps global Python clean. |
| System package managers (apt, yum, dnf on Linux) | ✅ Yes | Write to `/usr/bin`, `/etc`, `/var`. Root required for OS-wide software. |
| System services (Docker, PostgreSQL, nginx, Apache, MySQL, Redis) | ✅ Yes (install), ❌ daily use | Install touches system startup. Daily usage doesn’t usually need root. |
| Kernel extensions / device drivers (VPN, printer drivers) | ✅ Yes | Modify kernel/system. Only install from trusted sources. |
| Running scripts from internet (`curl … | sudo bash`) | 🚫 Dangerous unless official | Avoid unless trusted. Could run anything with root privileges. |
| Building from source with `make install` | ⚠️ Sometimes | Check where it installs: `/usr/local` → may need root, `~/.local/bin` → no root. |

---

## 🛠️ How to Decide (3 Quick Questions)
1. **Official docs say `sudo`?** → Safe to use it.  
2. **Where is it writing?**  
   - User folders (`~/`, `/opt/homebrew`) → no root.  
   - System folders (`/usr/bin`, `/etc`) → root.  
3. **What is it?**  
   - Dev tool just for you → no root.  
   - System service for everyone → root.  

---

## 🧠 Memory trick
- **Default = no sudo.**  
- **Use sudo only when:**  
  - Trusted source ✅  
  - Official instructions ✅  
  - System-level change ✅  
