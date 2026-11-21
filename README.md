# Native 360 Spine Editor — public runner

Dedicated public GitHub Actions execution host for the real PSD → Spine ZIP → licensed Spine Editor 4.3.26 → 40-frame native render task.

## Runner
- GitHub-hosted `ubuntu-latest`
- Workflow: `.github/workflows/runner.yml`
- Manual and scheduled execution
- The visual/unit audit scripts are mirrored in this repository; the private core workflow remains in `vladleopold/3Spine-core`.

## Required repository secrets
- `ACCESS_TOKEN`: read access to `SpineAnimator/spine-animator-private` and its Actions artifacts.
- `SPINE_LICENSE`: licensed Spine Editor activation.
- `SPINE_LINUX_URL`: authorized Linux distribution URL for Spine Editor 4.3.26.

The synthetic visual-gate tests already run on the public runner. Native Editor execution cannot proceed until these credentials are configured. No local iMac execution is used.
