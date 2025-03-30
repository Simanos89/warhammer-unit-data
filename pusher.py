import os
import subprocess

# Repository-instellingen
GITHUB_REPO = "https://github.com/Simanos89/warhammer-unit-data.git"
DATA_FOLDER = "data"

# Instellen van git config
def configure_git_user():
    subprocess.run(["git", "config", "--global", "user.name", "simanos89"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "s.wessemius@zenithsecurity.nl"], check=True)

# Initialiseer repo als deze nog niet bestaat
def initialize_git_repo():
    if not os.path.exists(".git"):
        print("📁 Geen git repo gevonden, initialiseren...")
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "branch", "-M", "main"], check=True)
        subprocess.run(["git", "remote", "add", "origin", GITHUB_REPO], check=True)

# Pull om remote wijzigingen te integreren
def pull_latest():
    try:
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=True)
    except subprocess.CalledProcessError:
        print("⚠️  Mislukt om te pullen. Controleer conflicten handmatig als dit blijft gebeuren.")

# Push de data-folder
def push_data():
    print(f"📦 Pushen van '{DATA_FOLDER}/' naar GitHub...")
    subprocess.run(["git", "add", "."], check=True)  # Voeg alles toe
    subprocess.run(["git", "commit", "-m", "🔄 Automatische update van data/"], check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], check=True)

if __name__ == "__main__":
    try:
        configure_git_user()
        initialize_git_repo()
        pull_latest()
        push_data()
        print("✅ Push succesvol!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Fout bij uitvoeren van: {e.cmd}")
