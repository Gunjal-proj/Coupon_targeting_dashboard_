# Project tracker

Tick items off as you go (on GitHub: open this file, click the pencil icon, change `[ ]` to `[x]`,
then **Commit changes**). Steps marked **(you)** need your accounts or your judgement; everything
else is already done in this repo.

## Phase 1 · Accounts (10 minutes)

- [ ] **(you)** Create a GitHub account at <https://github.com/signup>. Pick a professional
      username: it appears in your repository link.
- [ ] **(you)** Create a Netlify account at <https://app.netlify.com/signup> and choose
      **Sign up with GitHub**, so the two are linked from the start.

## Phase 2 · Put the code on GitHub (10 minutes)

- [ ] **(you)** Unzip `coupon-targeting-dashboard.zip` on your computer.
- [ ] **(you)** On GitHub, click **+** (top right) → **New repository**.
      Name it `coupon-targeting-dashboard`, set it to **Public**, leave
      "Add a README file" **unticked** (the project already has one), then **Create repository**.
- [ ] **(you)** On the empty repository page, click the **uploading an existing file** link.
- [ ] **(you)** Open the unzipped folder, select **everything inside it** (`README.md`,
      `netlify.toml`, `site`, `pipeline`, `docs`, `data`, ...) and drag it onto the page.
      Drag the contents, not the outer folder, or everything ends up one level too deep.
- [ ] **(you)** Commit message: `First version of the dashboard` → **Commit changes**.
- [ ] Check: the repository's front page shows `netlify.toml` and the `site` folder at the top level.

## Phase 3 · Publish on Netlify (10 minutes)

- [ ] **(you)** In Netlify: **Add new project** → **Import an existing project** → **GitHub**,
      approve access, and pick `coupon-targeting-dashboard`.
- [ ] **(you)** Build settings: leave the build command empty. The publish directory is `site`
      (the `netlify.toml` file sets this automatically; type `site` if a field asks).
      Click the publish/deploy button.
- [ ] **(you)** **Make it public.** New Netlify accounts start projects as private, so recruiters
      would see a "no access" page. Click **Make public** on the project, or go to
      **Project configuration → General → Visitor access → Project visibility** and choose public.
      Test the link in a private/incognito window.
- [ ] **(you)** Give it a clean name, such as `coupon-targeting-yourname`. The name becomes your
      link: `coupon-targeting-yourname.netlify.app`. Netlify offers this in the **Make public**
      step and in **Project configuration → General**.
- [ ] **(you)** Paste the live link at the top of `README.md` and in the footer of
      `site/index.html` (both are marked `EDIT`).

### Keeping it live

- Every commit to GitHub triggers a new deploy, and the site updates in about a minute.
- On Netlify's free plan each production deploy uses 15 of your 300 monthly credits, so about
  20 deploys a month. **Batch your edits**: upload several changed files in one commit. If the
  credits run out, Netlify pauses your sites until the next month.

## Phase 4 · Make it yours (your marketing calls)

- [ ] **(you)** Read the live dashboard top to bottom. List anything you could not explain to an
      interviewer, and ask Claude about each one.
- [ ] **(you)** Decide the simulator's default assumptions (cost to send, profit per new sale,
      share of new sales). They are placeholders today. Write one sentence on why you chose each.
- [ ] **(you)** Keep or rename the four segments (Engaged deal-seekers, Budget deal-seekers,
      Full-price loyalists, Light shoppers).
- [ ] **(you)** Rewrite the four recommendations in your own words and choose the one you lead with.
- [ ] **(you)** Put your name, LinkedIn and GitHub links in the footer and README.
- [ ] **(you)** Decide whether to add a line to the README saying it was built with an AI coding
      assistant. Being upfront about this tends to go down better in interviews than being asked.

## Phase 5 · Learn the story (interview prep)

- [ ] **(you)** Tell it in 60 seconds: problem (88% of mailings wasted) → data → approach →
      result (top 30% reaches 74% of redeemers) → recommendation (holdout test).
- [ ] **(you)** Prepare answers to:
  - Why rank households within each campaign instead of across all campaigns?
  - Why test on later campaigns instead of a random split? What is leakage, and how did you avoid it?
  - Why keep LightGBM when logistic regression scored about the same?
  - What does an AUC of 0.83 mean in plain words?
  - Why is a redemption not the same as an extra sale? How would you design the holdout test?
  - What would you do with the original AmExpert coupon-level data?
- [ ] Ask Claude for a one-page Q&A sheet on these.

## Phase 6 · Package it for your CV

- [ ] **(you)** CV bullet (edit to taste):
      *Built and deployed a coupon-targeting and ROI dashboard on 1.47M retail transactions
      (84.51° data), adapting the AmExpert 2019 winners' approach; ranking households reached 74% of
      redeemers while mailing 30% of them on held-out campaigns, and showed 78% of redemptions went to
      products customers already bought.*
- [ ] **(you)** LinkedIn post: the problem in one line, one screenshot, the live link, one lesson.
- [ ] **(you)** Two-minute screen recording (Loom or your phone): problem → tracker → model →
      simulator → recommendation.
- [ ] Optional: an 8-10 slide case deck (ask Claude to build it as Slides).
- [ ] **(you)** Pin the repository on your GitHub profile.

## Phase 7 · Optional upgrades

- [ ] Rebuild at customer × coupon level on the original AmExpert 2019 files, if you can download
      them from Analytics Vidhya. Keep those files out of this public repository: I could not find
      a licence that allows republishing them.
- [ ] Add a holdout-test planner: sample size needed to detect a given lift in spend.
- [ ] Add a short consumer survey on why people redeem coupons, to pair the numbers with reasons.

## Updating the numbers

The dashboard reads `site/assets/data.js`, which `python run_pipeline.py` regenerates
(about two minutes). Change settings in `pipeline/config.py`, rerun, and commit the new `data.js`.
