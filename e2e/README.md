```bash
gc -am . ; gp && ssh magisterka "cd magisterka && git pull && /nix/var/nix/profiles/default/bin/nix-shell --run 'cd e2e && terraform apply -auto-approve'" && say done
```
