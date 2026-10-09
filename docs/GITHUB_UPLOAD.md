# Upload this project to GitHub

## Option 1: use the GitHub website

This is the easiest method if you have not used Git before.

1. Download the project ZIP and choose **Extract All**. Open the extracted `personal-library-indexer` folder.
2. Sign in at [github.com](https://github.com/).
3. Open [github.com/new](https://github.com/new).
4. Set the repository name to **personal-library-indexer**.
5. Optional description: **Python desktop app that indexes PDF and EPUB books into a searchable CSV catalogue.**
6. Choose **Public** if your college needs to view it without an invitation. Public means anyone can see the repository. If your college requires a private submission, choose Private and give the evaluator access using your college's instructions.
7. Leave the README, .gitignore and license initialization options off; these files are included in the download. Click **Create repository**.
8. On the empty repository page, click **uploading an existing file**. On a repository that already has files, choose **Add file > Upload files**.
9. Open the extracted project folder. Drag its **contents** onto GitHub's upload area: the files and subfolders inside `personal-library-indexer`, keeping their structure. Upload the clean extracted copy before running it, so generated environments and indexes are not included.
10. Enter the commit message **Add Personal Library Indexer project**, then use **Commit changes**. GitHub may offer **Propose changes** instead when a branch workflow is required; follow that prompt to merge the upload.
11. Confirm that **README.md**, **app.py**, **cli.py**, and **requirements.txt** appear at the repository's top level. Check that `library_indexer/` and `sample_books/` are present.
12. Copy the repository URL from your browser and submit that link to your college.

**Upload the extracted source files, not just the ZIP.** A ZIP-only repository hides the code and does not display the README as the project homepage. Do not drag the outer folder as a single nested directory; open it and drag its contents.

The complete prepared project is small enough for one browser upload. GitHub allows up to 100 files at a time and 25 MiB per file in the browser. If a browser refuses a configuration file or you want easier updates, use Git or GitHub Desktop.

## Option 2: use Git

Install Git and create the empty GitHub repository as above. Open a terminal in the extracted project folder. Replace `YOUR_USERNAME` with your GitHub username:

```bash
git init -b main
git add .
git commit -m "Add Personal Library Indexer project"
git remote add origin https://github.com/YOUR_USERNAME/personal-library-indexer.git
git push -u origin main
```

If Git asks for a commit identity, set your chosen name and GitHub-associated or GitHub-provided no-reply email, then repeat the commit command. Follow GitHub's sign-in flow when prompted. Your GitHub account password is not used as a Git command-line password.

For later changes:

```bash
git add .
git commit -m "Describe the change you made"
git push
```

The included ignore rules keep local virtual environments, caches, personal book folders and generated indexes out of Git commits.

## What the evaluator does

1. Open your repository link and read the README.
2. Choose **Code > Download ZIP** and extract it, or clone the repository.
3. Install Python if needed.
4. On Windows, double-click `start_windows.bat`. The README also has manual commands for Windows, macOS and Linux.
5. Click **Try sample books**, search for `python`, and export the results.

GitHub stores the project code. The evaluator runs this **desktop application on their own computer**. GitHub Pages does not run Python desktop applications.

## Check before submission

- The repository's first page shows the project README.
- The sample books and source folders are included.
- You can run the project from the extracted folder on your computer.
- You can explain the scanning, genre rules and CSV export using `docs/PROJECT_EXPLANATION.md`.

Official help: [Create a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository), [upload files](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository), and [push existing code with Git](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).
