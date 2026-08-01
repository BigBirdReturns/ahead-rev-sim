; A bounded mixed hot/cold program used to prove the frontier artifact.
ADD r1, r0, 10
ADD r2, r0, 5
RMODADD r1, r2
RXOR r1, r3
STORE r0, r1, 64
LOAD r4, r0, 64
BEQ r4, r1, done
SUB r4, r4, 1
done:
HALT
