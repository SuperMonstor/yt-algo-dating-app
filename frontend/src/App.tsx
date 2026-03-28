import { motion } from 'framer-motion'
import './App.css'

const fade = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
}

const stagger = { show: { transition: { staggerChildren: 0.08 } } }

export default function App() {
  return (
    <>
      {/* Nav */}
      <div className="nav">
        <div className="nav-inner">
          <span className="nav-logo">vibe match</span>
          <a href="#join"><button className="nav-cta">Join waitlist</button></a>
        </div>
      </div>

      <div className="page">

        {/* ── Hero ──────────────────────── */}
        <motion.section
          className="s s-first t-center"
          initial="hidden"
          animate="show"
          variants={stagger}
        >
          <motion.p className="t-label mb-24" variants={fade}>
            A new way to meet people
          </motion.p>
          <motion.h1 className="t-hero mb-24" variants={fade}>
            Your YouTube already<br />knows your type
          </motion.h1>
          <motion.p className="t-body mb-40" style={{ maxWidth: 480, margin: '0 auto 40px' }} variants={fade}>
            We look at what you actually watch — not what you say you like —
            to find people you'd genuinely get along with.
          </motion.p>
          <motion.div variants={fade} style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            <a href="#join"><button className="btn btn-fill">Get your fingerprint</button></a>
            <a href="#how"><button className="btn btn-outline">How it works</button></a>
          </motion.div>
        </motion.section>

        <div className="s-divider" />

        {/* ── Thesis ─────────────────────── */}
        <motion.section className="s" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.h2 className="t-large mb-24" variants={fade}>
            Dating apps match on who you <span className="t-italic">say</span> you are.
            Not who you are.
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
          <motion.p className="t-label mb-12" variants={fade}>What we look at</motion.p>
          <motion.h2 className="t-large mb-24" variants={fade}>
            The things that make two people<br />click aren't in any profile
          </motion.h2>
          <motion.p className="t-body mb-20" variants={fade}>
            They're in the rhythm of what you consume. The pattern of topics you
            keep coming back to. Whether you watch 3-hour podcasts or 10-minute
            explainers. How niche your taste goes.
          </motion.p>
          <motion.p className="t-body" variants={fade}>
            We analyze every long-form video you've watched, tag each one with AI,
            and build a multi-dimensional profile of your taste — across
            <span className="t-accent"> topics, channels, formats, depth, </span>
            and domains. Then we score you against everyone else on six compatibility
            signals, weighted by how rare each overlap is.
          </motion.p>
        </motion.section>

        <div className="s-divider" />

        {/* ── How it works ───────────────── */}
        <motion.section className="s" id="how" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.p className="t-label mb-12" variants={fade}>How it works</motion.p>
          <motion.h2 className="t-large mb-40" variants={fade}>
            Three steps. Two minutes. Zero swiping.
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
                  We filter to long-form content, tag every video with AI, and
                  compute your taste profile. You'll see your personality type,
                  top topics, format preferences, and the niche stuff only you watch.
                </p>
              </div>
            </motion.div>
            <motion.div className="step-item" variants={fade}>
              <div className="step-num">3</div>
              <div className="step-content">
                <h3>Meet people who get it</h3>
                <p>
                  Our matching engine finds people with eerily similar taste.
                  Every match comes with shared topics, niche overlaps, and a
                  conversation starter so you're never starting from zero.
                </p>
              </div>
            </motion.div>
          </div>
        </motion.section>

        <div className="s-divider" />

        {/* ── Fingerprint preview ────────── */}
        <motion.section className="s t-center" initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.p className="t-label mb-12" variants={fade}>Your fingerprint</motion.p>
          <motion.h2 className="t-large mb-12" variants={fade}>
            This is what YouTube says about you
          </motion.h2>
          <motion.p className="t-body mb-48" variants={fade} style={{ maxWidth: 460, margin: '0 auto 48px' }}>
            A surprisingly honest portrait built from your actual behavior
          </motion.p>
          <motion.div className="fp-card" variants={fade}>
            <div className="fp-head">
              <div className="fp-badge">Polymath</div>
              <h3>Your YouTube Fingerprint</h3>
              <p>Interests spanning tech, philosophy, sports, and music</p>
              <div className="fp-meta">
                <span><strong>3,669</strong> videos</span>
                <span><strong>2,143</strong> channels</span>
                <span><strong>435</strong> hours</span>
              </div>
            </div>
            <div className="fp-body">
              <div className="fp-group">
                <div className="fp-group-title">Interest Map</div>
                <div className="fp-bars">
                  {[
                    { label: 'Music', pct: 22.2, color: '#c75a3a' },
                    { label: 'Sports', pct: 14.7, color: '#d4943a' },
                    { label: 'Entertainment', pct: 10.1, color: '#7b9e87' },
                    { label: 'Comedy', pct: 7.7, color: '#5a7db5' },
                    { label: 'Self-improvement', pct: 4.5, color: '#9b7fc4' },
                  ].map((b, i) => (
                    <div className="fp-row" key={i}>
                      <span className="fp-row-label">{b.label}</span>
                      <div className="fp-row-track">
                        <motion.div
                          className="fp-row-fill"
                          style={{ background: b.color }}
                          initial={{ width: 0 }}
                          whileInView={{ width: `${(b.pct / 22.2) * 100}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.7, delay: i * 0.06 }}
                        />
                      </div>
                      <span className="fp-row-val">{b.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="fp-group">
                <div className="fp-group-title">Top Topics</div>
                <div className="fp-tags">
                  {['reggaeton', 'edm', 'pop music', 'AR Rahman', 'indie pop',
                    'stoic philosophy', 'zone 2 training', 'startups'].map((t, i) => (
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
            Curious what YouTube<br />says about you?
          </motion.h2>
          <motion.p className="t-body mb-40" variants={fade} style={{ maxWidth: 420, margin: '0 auto 40px' }}>
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
          <motion.p className="t-small mb-0" variants={fade} style={{ marginTop: 20 }}>
            We never store your raw watch history. Privacy-first by design.
          </motion.p>
        </motion.section>

        {/* ── Footer ─────────────────────── */}
        <footer className="footer">
          <p>vibe match</p>
          <div style={{ marginTop: 8 }}>
            <a href="#">Privacy</a>
            <a href="#">Terms</a>
          </div>
        </footer>

      </div>
    </>
  )
}
