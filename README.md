# FOtT - *F*ive *O*ne *t*o *T*wo

An automation tool that makes dialog clearer when converting 5.1 surround audio into stereo, by boosting the center channel (where dialogue usually lives) while keeping the rest of the mix balanced.
## What it does

### Input: a typical 5.1 stream


                [ FC ]
             Center (dialog)

        [ FL ]         [ FR ]
      Front Left     Front Right


        [ SL ]         [ SR ]
     Surround L      Surround R

                [ SUB ]
                Subwoofer

### Downmix strategy (5.1 → 2.0)

#### Left output

    FC ──(×1.2)─────────┐
                        ├──► LEFT OUT [L]
    FL ──(×0.7)─────────┤
                        │
    SL ──(×0.7)─────────┘


    
 #### Right output

    FC ──(×1.2)─────────┐
                        ├──► RIGHT OUT [R]
    FR ──(×0.7)─────────┤
                        │
    SR ──(×0.7)─────────┘

## Result
- Dialog is more prominent (boosted center channel)
- Less “volume riding” during high dynamic range scenes (action/music vs. speech)
- Still sounds like the original mix, just with clearer speech

## Usage
- run `fott.py` in any directory with video files
    - use `--dry` to perform a dry run


