import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import sys
import os
from pathlib import Path

# --- Helper function to run AIOS demo as a subprocess ---
def _run_aios_in_thread(gui_instance, user_instruction, api_key, on_complete_callback):
    # Determine the path to aios_demo.py
    # This assumes gui.py is in the project root and aios_demo.py is also in the project root
    aios_demo_path = Path(__file__).parent / "aios_demo.py"
    
    # Use the current Python executable from the virtual environment
    python_executable = sys.executable

    # Prepare command with arguments
    command = [
        python_executable,
        str(aios_demo_path),
        "--user_instruction", user_instruction,
    ]
    
    # For now, always use mock LLM. This can be made configurable later.
    command.extend(["--llm_use_mock", "True"])
    
    if api_key:
        command.extend(["--llm_api_key", api_key])

    gui_instance.log_status(f"Executing: {' '.join(command)}")
    
    # Start the subprocess
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Redirect stderr to stdout
        text=True, # Decode stdout/stderr as text
        bufsize=1 # Line-buffered output
    )

    # Stream output to GUI
    for line in iter(process.stdout.readline, ''):
        gui_instance.master.after(0, gui_instance.log_status, line.strip()) # Update GUI from main thread
    
    process.stdout.close()
    process.wait() # Wait for process to finish

    gui_instance.master.after(0, on_complete_callback, process.returncode) # Call callback when complete

class AIOSGui:
    def __init__(self, master):
        self.master = master
        master.title("AIOS Demo Controller")
        master.geometry("600x450")

        # LLM API Key Input
        self.api_key_label = tk.Label(master, text="LLM API Key (ignored for mock server):")
        self.api_key_label.pack(pady=(10, 0))
        self.api_key_entry = tk.Entry(master, width=50, show="*")
        self.api_key_entry.pack(pady=(0, 10))

        # User Instruction Input
        self.instruction_label = tk.Label(master, text="User Instruction:")
        self.instruction_label.pack()
        self.instruction_text = scrolledtext.ScrolledText(master, wrap=tk.WORD, width=60, height=10)
        self.instruction_text.pack(pady=(0, 10))

        # Run Button
        self.run_button = tk.Button(master, text="Run AIOS Demo", command=self.run_aios_demo)
        self.run_button.pack(pady=(0, 10))

        # Status Output
        self.status_label = tk.Label(master, text="Status:")
        self.status_label.pack()
        self.status_output = scrolledtext.ScrolledText(master, wrap=tk.WORD, width=60, height=5, state=tk.DISABLED)
        self.status_output.pack(pady=(0, 10))

    def log_status(self, message):
        self.status_output.config(state=tk.NORMAL)
        self.status_output.insert(tk.END, f"{message}\n")
        self.status_output.see(tk.END) # Scroll to the end
        self.status_output.config(state=tk.DISABLED)

    def run_aios_demo(self):
        api_key = self.api_key_entry.get()
        user_instruction = self.instruction_text.get("1.0", tk.END).strip()

        if not user_instruction:
            messagebox.showwarning("Input Error", "Please provide a user instruction.")
            return

        self.run_button.config(state=tk.DISABLED)
        self.log_status("AIOS Demo started...")
        self.log_status(f"LLM API Key: {'*' * len(api_key) if api_key else 'None Provided'}")
        self.log_status(f"User Instruction: {user_instruction}")
        
        # Start the AIOS demo in a separate thread
        self.aios_thread = threading.Thread(target=_run_aios_in_thread, 
                                            args=(self, user_instruction, api_key, self._on_aios_complete))
        self.aios_thread.daemon = True # Allow program to exit even if thread is running
        self.aios_thread.start()

    def _on_aios_complete(self, returncode):
        if returncode == 0:
            self.log_status("AIOS Demo finished successfully.")
        else:
            self.log_status(f"AIOS Demo failed with exit code: {returncode}")
        self.run_button.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    my_gui = AIOSGui(root)
    root.mainloop()