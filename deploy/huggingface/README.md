---
title: Arithmetic Coding Showcase
emoji: 🗜️
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 6.32.0
python_version: "3.13"
app_file: app.py
short_description: Squeeze text into bits with language models
pinned: false
license: mit
---

# Fewer bits, by guessing the next letter

An interactive showcase of **arithmetic coding with language models**: a model guesses each next
letter, and the better it guesses, the fewer bits the message needs. Watch it encode your text step by
step, compare two encoders, and meet the ten encoders (from a 0.8M-parameter Shakespeare model to
GPT-2).

Code, studies and how it works: https://github.com/GalAshkenazi1/ArithmeticCoder

This Space's `app.py` downloads a tagged release of that repository when it starts, then runs the
repository's own web server (FastAPI). It uses the Gradio SDK only to install Python and the packages
in `requirements.txt`; the pages are not a Gradio app. See the repository's `deploy/huggingface/`.
