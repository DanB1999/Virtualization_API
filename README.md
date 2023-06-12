# Virtualization_API
REST-API zur Steuerung und Verwaltung von Virtuellen Maschinen und Containern, im Rahmen einer Bachelorarbeit


# Starten der App:
uvicorn main:app --reload

# Funktionen:
Docker:
Auflisten von Containern und Images 
Informationen über Container
Starten, Stoppen und Neustarten von Containern
Löschen von Containern 
Erstellen von Containern (docker run)

Qemu/kvm:
Auflisten von VMs und Snapshots
Informationen über VM
Starten, Stoppen (Pausieren), Neustarten und Herunterfahren von VMs
Löschen von VMs
Erstellen von VMs
