# Design notes and project history

> **Status: historical.** This document records the original planning paper and
> the scope decisions made during development. Parts of it describe an earlier
> stack (Reflex, Gemini, Deepgram, Watson, OpenRouter); the shipped app uses
> React + FastAPI and a single Requesty gateway for all model calls.
> [`README.md`](../README.md) and the source code are authoritative.

---

TECHNICAL PLANNING

As we move through the development phase of MBDT, the project has shifted from research and planning into active production, and I have spent the past weeks immersed in building both the frontend and backend using Python and React + JS (we decided to switch from Reflex to React for web development due to more support and flexibility). At this midpoint, the core SQLite database and Bayesian forgetting algorithm that dynamically targets weak words are largely functional behind the scenes, yet translating these backend mechanics into an intuitive, child-friendly interface remains very much in progress. One of the most significant hurdles I have faced is integrating third-party services, Gemini for LLM generation, Deepgram for STT, and IBM Watson for TTS, while maintaining our strict privacy promise that all user data stays strictly local; routing API calls through Openrouter to ensure zero-data-retention compliance has added architectural complexity that I had not fully anticipated. We also had to make difficult cuts: I could not source consistent, open-license phoneme videos for Exercise 2, and real time STT streaming for longer fluency passages in Exercise 4 proved both too costly and too latency heavy for our local deployment model, forcing us to narrow our scope to three core exercises. Restricting the app to laptops due to Reflex and hardware constraints has also been frustrating, as it limits accessibility despite our inclusive intentions. Throughout this process, I have relied on Cameron to safeguard the pedagogical integrity of our Orton Gillingham approach while I navigate the technical tradeoffs of implementation. This middle phase has taught me that even the most carefully planned research does not map neatly to code, and that building a tool for vulnerable users requires constantly balancing idealism with what is technically feasible. Still, I am gaining confidence that the adaptive, locally deployable system.

Derek Wu et. al

The project is a locally-deployable website where we recreate established dyslexia therapy treatments digitally. We enhance user experiences by using machine learning to change the difficulty of individual exercise components to target the weak spots of users’ literacy deficits. For example, we use evolutionary learning to target what fonts, words and phonics the user struggles with, and use LLMs with context engineering to generate stories according to the user’s interests. (We have safety guards to prevent inappropriate generation beyond that set by the model provider; we allow the user to select categories and elements only) This is meant to be a supplemental exercise to be fun and engaging for children with literacy deficits compared to the rather dull existing therapies, not as an alternative to professional help. That being said, we hope to be able to provide at least some extent of help to those who cannot afford proper care.
Here are the main exercises and features of our website:
Exercise 1: Words will appear and move across the screen of different fonts (dynamically selected to target weaknesses) where the user has to speak and a STT model will attempt to recognize and check whether the user’s pronunciation is correct. This is done for previously learnt words at the start of the section to enhance their memory.


Exercise 3: This will once again target weak words. The user will attempt to write out existing words, based on sound. The user will also attempt to category words based on a given phoneme. 


Exercise 5: LLMs (with safeguards) will generate stories based on learnt phonemes, words, and newly learnt words (same session). The user will be asked to answer basic reading comprehension answers based on the generated text.


Introduction

We should start by clarifying that this tool aims to be a supplementary exercise software, not a replacement for professional literacy therapy.

Due to limited technical capabilities, we intend to use python for the language for developing the app, focusing on running on laptops and PCs for the near term beta-testing. Python offers a quick, easy, accessible way for innovation that suits our need for fast pace, flexible development, to verify the capabilities and direction of our app.

For the development of this application, we have selected Reflex as our primary UI library. Unlike traditional Python GUI frameworks like Tkinter or heavy game engines like Pygame, that have thread safety issues and require significant effort for basic components, Reflex allows us to build interfaces using a Python-based wrapper around React and FastAPI.

By using Reflex, we inherit a native asynchronous architecture which is crucial for many of the high(er) latency exercises. It allows the application to handle high-latency operations, such as calling the Gemini LLM or IBM Watson TTS, without freezing the user interface. 

Specifications

For the early phase of development (as a CAS project) we intend to restrict development to a single-player experience, in order for maximum development speed and flexibility before entering wider network-based or as an online service. This decision is also done to ensure the privacy of the patients during testing, as all data are solely stored on their local devices, and any form of access of data for research purposes from us will require us to physically meet and obtain the explicit permission from patients and guardians.

Aesthetic wise, to suit a wide range of audience, we intend to use a minimalistic, clean interface with neon-pastel primary colors as accents. The UI will be round, simplistic, but with distinguishable shapes in order to be accessible to colorblind users.

Furthermore, we require access to many third party services, notably LLM generated reading comprehension tuned for the user’s need, as well as TTS, STT and OCR for writing and recognition practices. These services need to be offloaded to online providers to be accessible to lower end devices, such that we are inclusive to marginalized communities.

For said needs, we intend to use:
Google Gemini Flash 3 for our LLM and OCR needs via Openrouter
For TTS, we intend to use IBM Watson TTS Service
For STT, we intend to use Deepgram STT Service
Justification of Design Choices


LLM Usage
We chose to use Google Gemini 3 Flash due to it being the SOTA for visual understanding, low latency, and high intelligence, making it highly suitable for both visual accuracy (needed for OCR) and high intelligence (needed for dynamic generation of reading comprehension). Low latency and high throughput also allows for the optimal experience for users, minimizing waiting time. Openrouter is a routing service allowing ease of access to Gemini services globally, without region restrictions, for maximum accessibility. They also ensure that all services conducted with Gemini are under a zero-data-retention (ZDR) policy, ensuring providers are legally obliged to never be stored, ensuring the privacy of users.

Openrouter’s routing service also ensures that our user’s usage is mixed within an abundant traffic flow, hence implicitly removing the link from i.e. a regular Google Account to its usage. Openrouter itself also ensures our privacy by stating their legal obligations in their policy. No personally identifiable information will be included in prompts.

During the test phase, each participant will receive API keys for the relevant services. They will be paid for by the researchers; we are unable to see the content nor activity of participants, only their volumetric activity.


TTS Usage
We chose to use IBM Watson TTS due to it being free of cost, minimizing both development, service, and user’s burden. It has sufficient quality for our use case, that being singular words, and offers a generous free plan of 10,000 characters per month, translating to roughly 2,000 (new) words per month, which is more than sufficient for individuals. Our usage has minimal effects on privacy (singular words, no prompt or additional information is externalized), hence a free plan would be sufficient for our use case, and no additional practices would be needed to ensure privacy in this section.

STT Usage
We chose to use Deepgram STT due to it offering a free plan of $200 per new account, sufficient for our use case during testing. It is needed to facilitate the pronunciation-checking mechanics in Exercise 1, we need to integrate Deepgram for the STT processing. The service is among the fastest, and has strict privacy policies (ZDR compliant). It also offers confidence scores that makes it suitable for our program, making it more adaptive i.e. confidence scheduling; requiring the user to make more precise pronunciation in later stages. We have considered more private options like Google’s STT or potentially local models, but they are oftentimes complex, high latency, or resource intensive, rendering them unsuitable for our use case.


Key Algorithm

As noted in the introduction, we are using sqlite3 for backend. Backend components are quite standard, and require minimal discussion besides algorithms. We will be using a Bayesianic Forgetting Model shared across all exercises, to surgically target words that the user finds difficult, and via repetition, will hopefully be able to learn said words. The generated reading comprehension will also be generated with the user’s top-k difficult words in mind, and results likewise contribute to the system. Guardians may select a certain set of words i.e. cambridge-prelimary-vocabulary set as the source of words their child should learn.

However, the system is not quite interpretable, and ignores comprehension accuracy. For measuring patient performance with a singular, unified variable, we aggregate the mean word accuracy and comprehension accuracy together to produce the composite score.


Revisions

Regarding revisions, we originally planned for 5 exercises, but we have removed Ex. 2 and Ex. 4. From early testing and research, we have concluded that we cannot source, a consistent, open license, high-quality videos of people speaking phonemes that fit our needs, eliminating Ex. 2. We also found that STT (speech to text) models actually cost a lot especially for repeated, long paragraph speech, and real time streaming back recognition to our device is quite hard to do, hence eliminating Ex. 4.
