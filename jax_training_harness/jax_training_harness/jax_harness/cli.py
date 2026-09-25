import argparse
from pathlib import Path
from .config import HarnessConfig
from .experiment import run_experiment

def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the structured JAX training harness')
    parser.add_argument('--steps', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--seq-len', type=int, default=32)
    parser.add_argument('--d-model', type=int, default=64)
    parser.add_argument('--checkpoint', type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = HarnessConfig(batch_size=args.batch_size, seq_len=args.seq_len, d_model=args.d_model)
    trainer, history = run_experiment(cfg, args.steps)
    print('summary:', trainer.summary(history))
    if args.checkpoint:
        trainer.save(args.checkpoint, {'config': cfg.to_dict(), 'summary': trainer.summary(history)})
        print('saved:', args.checkpoint)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
