import { motion } from 'framer-motion'
import './App.css'

const fade = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

const stagger = { show: { transition: { staggerChildren: 0.06 } } }

export default function App() {
  return (
    <>
      {/* Nav */}
      <div className="nav">
        <div className="nav-inner">
          <span className="nav-logo">TASTE<span className="nav-logo-accent">.</span></span>
          <a href="#join"><button className="nav-cta">Get your fingerprint</button></a>
        </div>
      </div>

      <div className="page">

        {/* ── Hero ──────────────────────── */}
        <motion.section
          className="s s-first"
          initial="hidden"
          animate="show"
          variants={stagger}
        >
          <motion.p className="t-label mb-24" variants={fade}>
            Your YouTube knows more than your bio
          </motion.p>
          <motion.h1 className="t-hero mb-32" variants={fade}>
            Your watch history<br />
            is your personality<span className="t-accent">.</span>
          </motion.h1>
          <motion.p className="t-body mb-40" style={{ maxWidth: 520 }} variants={fade}>
            We analyze what you actually watch — not what you say you like —
            and build a fingerprint of who you really are. Then we find people
            who'd genuinely get you.
          </motion.p>
          <motion.div variants={fade} style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <a href="#join"><button className="btn btn-fill">Get your fingerprint</button></a>
            <a href="#how"><button className="btn btn-outline">How it works</button></a>
          </motion.div>
        </motion.section>

        <div className="s-divider" />

        {/* ── Thesis ─────────────────────── */}
        <motion.section className="s" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.p className="t-label mb-16" variants={fade}>The problem</motion.p>
          <motion.h2 className="t-large mb-24" variants={fade}>
            Dating apps match on who you <span className="t-italic">say</span> you are<span className="t-accent">.</span><br />
            Not who you are<span className="t-accent">.</span>
          </motion.h2>
          <motion.p className="t-body mb-20" variants={fade}>
            Your bio says "love hiking." So does everyone else's. Self-reported
            preferences are performative. You write them for an audience.
          </motion.p>
          <motion.p className="t-body mb-32" variants={fade}>
            But your YouTube history at 2am? The obscure podcast you replayed
            three times? The 5,000-subscriber channel only you and twelve other
            people follow? That's the unfiltered version of who you are.
          </motion.p>
          <motion.div className="callout" variants={fade}>
            <p className="t-body">
              Two people who independently found the same niche creator
              probably have more in common than two people who both wrote
              <span className="t-accent"> "coffee enthusiast" </span>
              in their bio.
            </p>
          </motion.div>
        </motion.section>

        <div className="s-divider" />

        {/* ── What we see ────────────────── */}
        <motion.section className="s" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.p className="t-label mb-16" variants={fade}>What we look at</motion.p>
          <motion.h2 className="t-large mb-24" variants={fade}>
            The things that make two people click<br />
            aren't in any profile<span className="t-accent">.</span>
          </motion.h2>
          <motion.p className="t-body mb-20" variants={fade}>
            They're in the rhythm of what you consume. The pattern of topics you
            keep coming back to. Whether you watch 3-hour podcasts or 10-minute
            explainers. How niche your taste goes.
          </motion.p>
          <motion.p className="t-body" variants={fade}>
            We analyze every long-form video you've watched and build a
            multi-dimensional profile of your taste — across
            <span className="t-accent"> topics, channels, formats, depth, </span>
            and domains. Then we score you against everyone else, weighted
            by how rare each overlap is.
          </motion.p>
        </motion.section>

        <div className="s-divider" />

        {/* ── How it works ───────────────── */}
        <motion.section className="s" id="how" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.p className="t-label mb-16" variants={fade}>How it works</motion.p>
          <motion.h2 className="t-large mb-40" variants={fade}>
            Three steps<span className="t-accent">.</span> Two minutes<span className="t-accent">.</span><br />
            Zero swiping<span className="t-accent">.</span>
          </motion.h2>
          <div className="steps-list">
            <motion.div className="step-item" variants={fade}>
              <div className="step-num">1</div>
              <div className="step-content">
                <h3>Export your YouTube data</h3>
                <p>
                  Download your watch history from Google Takeout and upload the
                  file. We process it in memory and never store the raw data.
                </p>
              </div>
            </motion.div>
            <motion.div className="step-item" variants={fade}>
              <div className="step-num">2</div>
              <div className="step-content">
                <h3>See your fingerprint</h3>
                <p>
                  We filter to long-form content, embed every video, and
                  compute your taste profile. You'll see your interest DNA,
                  niche channels, comfort content, and a personality portrait
                  that's surprisingly accurate.
                </p>
              </div>
            </motion.div>
            <motion.div className="step-item" variants={fade}>
              <div className="step-num">3</div>
              <div className="step-content">
                <h3>Meet people who get it</h3>
                <p>
                  Our matching engine finds people with eerily similar taste.
                  Every match comes with shared niches and a conversation
                  starter so you're never starting from zero.
                </p>
              </div>
            </motion.div>
          </div>
        </motion.section>

        <div className="s-divider" />

        {/* ── Fingerprint preview ────────── */}
        <motion.section className="s" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.p className="t-label mb-16" variants={fade}>Your fingerprint</motion.p>
          <motion.h2 className="t-large mb-12" variants={fade}>
            This is what YouTube<br />says about you<span className="t-accent">.</span>
          </motion.h2>
          <motion.p className="t-body mb-48" style={{ maxWidth: 480 }} variants={fade}>
            A surprisingly honest portrait built from your actual behavior.
            Not what you tell people you watch.
          </motion.p>
          <motion.div className="fp-card" variants={fade}>
            <div className="fp-head">
              <div className="fp-badge">The Endurance Junkie</div>
              <h3>Your YouTube Fingerprint</h3>
              <p>Cycling, running, tennis, F1 — you don't just watch sports. You study them.</p>
              <div className="fp-meta">
                <span><strong>4,057</strong>videos</span>
                <span><strong>2,143</strong>channels</span>
                <span><strong>435</strong>hours</span>
              </div>
            </div>
            <div className="fp-body">
              <div className="fp-group">
                <div className="fp-group-title">Interest DNA</div>
                <div className="fp-bars">
                  {[
                    { label: 'Stoic philosophy', pct: 15 },
                    { label: 'Triathlon training', pct: 11 },
                    { label: 'Tennis highlights', pct: 10 },
                    { label: 'Comedy sketches', pct: 10 },
                    { label: 'The Office clips', pct: 9 },
                    { label: 'Formula 1', pct: 8 },
                    { label: 'Personal finance', pct: 7 },
                    { label: 'Cycling gear', pct: 7 },
                  ].map((b, i) => (
                    <div className="fp-row" key={i}>
                      <span className="fp-row-label">{b.label}</span>
                      <div className="fp-row-track">
                        <motion.div
                          className="fp-row-fill"
                          initial={{ width: 0 }}
                          whileInView={{ width: `${(b.pct / 15) * 100}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.6, delay: i * 0.05 }}
                        />
                      </div>
                      <span className="fp-row-val">{b.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="fp-group">
                <div className="fp-group-title">What defines you</div>
                <div className="fp-tags">
                  {['stoic philosophy', 'ironman triathlon', 'cycling gear reviews',
                    'running shoe comparison', 'the office nbc', 'bb ki vines',
                    'formula 1 racing', 'ai startups', 'personal finance'].map((t, i) => (
                    <span className="fp-tag" key={i}>{t}</span>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </motion.section>

        <div className="s-divider" />

        {/* ── Final CTA ──────────────────── */}
        <motion.section className="s t-center" id="join" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.h2 className="t-large mb-20" variants={fade}>
            Curious what YouTube<br />says about you<span className="t-accent">?</span>
          </motion.h2>
          <motion.p className="t-body mb-40" variants={fade} style={{ maxWidth: 440, margin: '0 auto 40px' }}>
            Upload your watch history and get your fingerprint.
            Free, private, and surprisingly revealing.
          </motion.p>
          <motion.div variants={fade}>
            <button
              className="btn btn-fill"
              onClick={() => alert('Coming soon!')}
            >
              Get your fingerprint
            </button>
          </motion.div>
          <motion.p className="t-small" variants={fade} style={{ marginTop: 24 }}>
            We never store your raw watch history. Privacy-first by design.
          </motion.p>
        </motion.section>

        {/* ── Footer ─────────────────────── */}
        <footer className="footer">
          <p>TASTE<span style={{ color: 'var(--accent)' }}>.</span></p>
          <div style={{ marginTop: 8 }}>
            <a href="#">Privacy</a>
            <a href="#">Terms</a>
          </div>
        </footer>

      </div>
    </>
  )
}
