# arithmetic coding POC

we will build a working app that sends messages encoded using arithmetic coding.

core ideas:
- two users that wishes to connect choose a gen-text model. the model is obligated to have char predictions, it takes a 'msg_start' and return the probabilities of each char to be the next, it has a pre-defined char-corpus (+EOT).
- a 'modelwrapper' class holds the model and defines the API to bridge between diffrent models and corpus lengths (for exampel, some models may not diffrentiate 'A' from 'a', leading to half-sized char corpus)
- coding is done step-by-step, each time asking the model "given the message so for, what are the probabilities of the next chars?", then "zooming" into the corresponding range.

## example of coding

char corpus: {a,b,c}

massage: "aabc"

fisrt round:
1. starting in full range [0,1]
2. ask the model for probabilities ('msg_start'="")
3. got [0.5, 0.25, 0.25]
4. update range to [0,0.5]

second round:
1. ask the model for probabilities ('msg_start'="a")
2. got [0.4, 0.4, 0.2]
3. update to range [0,0.2]

third round:
1. ask the model for probabilities ('msg_start'="aa")
2. got [0.2, 0.4, 0.2]
3. update to range [0.04,0.08]

4th round:
1. ask the model for probabilities ('msg_start'="aab")
2. got [0.1, 0.1, 0.8]
3. update to range ...

what's important: we finish with a range, and we want to shortest big-represented float to "land" in that range. we send that big-represented float + msg length.

## how decoding works
- get the float representing the msg + the length
- go 'length' times down the range-scheme 