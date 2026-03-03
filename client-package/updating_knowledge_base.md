# How to Update Your Knowledge Base

This guide explains how to add new information (documents or chats) to the AI's knowledge base so it can reference them in future conversations.

## 📁 1. Where do files go?

Open the `knowledge_base` folder inside your `emotional-rag` directory. You will see two folders:

- **`Chats`** — Put your downloaded ChatGPT `.json` export files here.
- **`docs`** — Put any plain text documents (`.txt` files) here.

> **Important:** The system only accepts `.json` (for chat exports) and `.txt` (for text documents). Word documents (`.docx`) or PDFs will be ignored and must be converted to plain text first.

---

## 🛑 2. How to Add New Files (Instant)

The AI watches this folder while it's running. **You do not need to restart** to add brand new files.

1. **Add Your Files**
   - Copy your new `.txt` files into `knowledge_base\docs\`.
   - Copy your new `.json` files into `knowledge_base\Chats\`.
2. **Wait 10 Seconds**
   - The system automatically detects the new file and processes it into its memory in the background. It is immediately ready to discuss.

---

## 🔁 3. How to Edit or Remove Existing Files

If you **edit** a file already in the folder, or **delete** a file so the AI forgets it, the automatic watcher won't perfectly sync those changes. You must force a memory reset:

1. Double-click `stop-windows.bat`. Wait for it to close.
2. Make your edits or delete your files.
3. Double-click `start-windows.bat`. The system will wipe its old memory and perfectly rebuild it from whatever is currently in the folder.

---

## 🧠 4. What Happens Under the Hood?

When you run `start-windows.bat`, the system automatically:
1. Deletes the old memory manifest.
2. Scans the `knowledge_base` folder.
3. Reads every file again and converts them into "vector embeddings".
4. Saves them securely into the database so the AI perfectly remembers them.

Because it scans everything from scratch every time you restart, **you must never delete old files from the folder** unless you want the AI to permanently forget them.

---

## 🛠️ Troubleshooting

- **"I added a file while it was running, but the AI doesn't know about it."** 
  You must fully stop the system (`stop-windows.bat`) and restart it (`start-windows.bat`) for new files to be read.
  
- **"I deleted a file, but the AI still remembers it."**
  Stop the system, make sure the file is actually gone from the `knowledge_base` folder, and start the system again. The system deletes all memory and rebuilds it based *only* on the files currently sitting in those folders.

- **"My text isn't being read."**
  Ensure your text files end in exactly `.txt` and your chat files end in exactly `.json`. Other formats are ignored to prevent crashes.
