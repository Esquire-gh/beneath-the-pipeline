# Writing style

Every page on this site is trying to do one thing: help someone understand
how a retrieval pipeline actually works. Clever compression reads as
confusion to a learner, so the writing here is deliberately plain. What
follows is the standard the pages are held to.

## Write in full, flowing sentences

Write the way a person explains something out loud. Sentences connect to
each other and carry the reader forward. Do not write in fragments for
effect.

> **No.** Same bytes. Same disk. Different answer.
>
> **Yes.** The bytes on disk have not changed and neither has the disk, yet
> the two tools report different sizes, because they are reading two
> different fields.

## Use almost no em dashes

They were everywhere and they made the prose feel chopped up. Reach for a
comma, a period, or a colon instead. The rare em dash that survives should
be doing something a comma genuinely cannot.

## Headings say what the reader is about to learn

A heading is a plain title, not a hint and not a joke. It should describe
the thing the section teaches, in the words a reader would use.

| Instead of | Write |
| --- | --- |
| `Chunk & Embed — text becomes vectors` | `Chunk & Embed — how text becomes vectors` |
| `Chunking first, and honestly` | `What these stages do, and why the pipeline needs them` |
| `Symptom` | `The puzzle` |
| `Ground` | `Mental Model` |

A heading that reads as cryptic is a heading to rewrite. If a reader cannot
tell from the heading alone what they are about to learn, it has failed.

## Explain the concept before the puzzle or the experiment

Every module opens with a plain description of the thing itself: what this
stage is, what it is for, and roughly how it is done. Only then comes the
puzzle, and only after that the commands to run.

The module page skeleton follows that order:

1. **What this module is about** — the concept, described plainly
2. **The puzzle** — two facts that collide, ending in a question
3. **Mental Model** — where a picture of the machinery helps, before the work
4. **Build it yourself** / **Investigate it yourself** — the commands
5. **What you should see** — the expected result
6. **Why it behaves this way** — the explanation
7. **How this fits the pipeline** — the connection back
8. **Read further, then check yourself** — the reading and the questions

A reader should never meet an experiment before they know what it is an
experiment about.

## State a puzzle as a set-up, then a question

The set-up gives the concrete facts. The question is a real question, asked
in one sentence.

> **No.** Two sentences: the cat sat on the mat and a feline rested upon
> soft carpet. They share no words at all. The pipeline scores them 0.550
> similar. What is being compared, if not words?
>
> **Yes.** Given two sentences that share no words in common, how can their
> similarity score be 0.550? What is being compared?

## Explain data representation from the top down

Start where the reader already lives and work downward to the bytes. The
order that works:

1. People think in numbers, text, images, audio, and video, and we write
   those concepts down using letters, digits, and other marks.
2. A single number is easy to hold in your head, and so is a piece of text.
   The hard question is what those become once they are a file on a disk,
   and how something like audio or video becomes a file at all.
3. A computer stores nothing but zeros and ones, so every one of those
   concepts has to be represented in that alphabet. A format is the written
   agreement that says how.
4. A PDF is one such agreement, and it describes the appearance of a page
   rather than a stream of sentences.
5. Loading a PDF gives you the PDF's own bytes in memory. It is still a PDF.
   Parsing is the separate act of converting from one agreement into
   another, which is how those bytes become text.

The same shape applies to every other stage: name the human concept, then
the representation, then what converting between representations costs.

## Tools confirm understanding, they do not supply it

A hex dump is a way to check that what you were told is true. It is not
where the understanding comes from, and a reader who has never opened one
should not be sent to it for their first explanation. Explain the idea in
prose first, then let the tool confirm it.

## The test to apply to any page

Before a page is done, ask three questions of it:

1. Will this build a mental model of what the concept is?
2. Will it help the reader understand what a high level implementation of
   the concept looks like?
3. Does it meet the standards above?

If the answer to any of them is no, the page gets rewritten.

## Mechanical checks

These are the checks run over the built site, not judgements of taste:

- No unresolved `{{ }}` measurement tokens, so no number is ever typed by
  hand.
- No broken internal links.
- No hedging or dismissive filler: `simply`, `obviously`, `of course`,
  `clearly`, `merely`, `trivially`. A word that tells the reader something
  is easy only makes them feel worse when it is not.
- Every module page carries its concept-first opening section.
