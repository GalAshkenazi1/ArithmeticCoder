---
title: Arithmetic Coding Showcase
emoji: 🗜️
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
short_description: Squeeze text into bits with language models
pinned: false
---

# Fewer bits, by guessing the next letter

An interactive showcase of **arithmetic coding with language models**: a model guesses each next
letter, and the better it guesses, the fewer bits the message needs. Watch it encode your text step by
step, compare two encoders, and meet the ten encoders (from a 0.8M-parameter Shakespeare model to
GPT-2).

Code, studies and how it works: https://github.com/galashkenazi1/ArithmeticCoder

This Space builds from a tagged release of that repository (see its `deploy/huggingface/`).
