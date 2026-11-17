'use client'

import { useState } from 'react'
import Link from 'next/link'
import BuilderPreview from '@/components/builder-preview'
import BrandLogo from '@/components/brand-logo'
import { ArrowRight, BriefcaseBusiness, Check, Code2, Grid2X2, Menu, Search, Sparkles, Users, X } from 'lucide-react'
import './home-enhancements.css'

function Logo() { return <BrandLogo href="#top" className="logo" /> }
function Character({ label, tone = 'blue', flip = false }: { label: string; tone?: string; flip?: boolean }) {
  return <div className={`character ${flip ? 'flip' : ''}`}><span className={`char-label ${tone}`}>{label}</span><div className="head"><div className="hair"/><div className="face"/><div className="glasses"/></div><div className={`body ${tone}`}><span className="laptop">&lt;_&gt;</span></div></div>
}

export default function Page() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <main id="top" className="home-page-neo">
      {/* Navbar */}
      <nav className="navbar">
        <div className="container nav-inner">
          <Logo />
          <div className="nav-links">
            <Link className="active" href="#top">Home</Link>
            <Link href="/builder/upload">Build Portfolio</Link>
            <Link href="/arena">Coding Arena</Link>
            <Link className="tech-hub-link" href="/tech-hub">Tech Hub</Link>
          </div>
          <div className="nav-actions">
            <button className="icon-button" aria-label="Search"><Search size={16}/></button>
            <Link href="#login" className="login">Log in</Link>
            <Link href="#signup" className="button orange small">Sign up</Link>
          </div>
          <button className="mobile-menu" aria-label="Open menu" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X/> : <Menu/>}
          </button>
        </div>
        {mobileOpen && (
          <div className="mobile-nav">
            {[
              ['Home', '/'],
              ['Build Portfolio', '/builder/upload'],
              ['Coding Arena', '/arena'],
              ['Tech Hub', '/tech-hub'],
            ].map(([label, href]) => (
              <Link key={label} href={href} onClick={() => setMobileOpen(false)}>
                {label}
              </Link>
            ))}
          </div>
        )}
      </nav>

      {/* Neo-Brutalist Developer Identity Hero Section (Matching Image 2) */}
      <section className="hero-neo">
        <div className="container hero-neo-container">
          {/* Left Column: Headline, Action Badges, Copy, CTAs, Tags */}
          <div className="hero-neo-left">
            <div className="hero-neo-eyebrow">
              <span>// ONE PLATFORM FOR DEVELOPERS</span>
            </div>

            <h1 className="hero-neo-title">
              Build Your<br />
              <span className="hero-neo-title-accent">
                Developer Identity.
                <svg className="hero-neo-wave" viewBox="0 0 310 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M3 11C24 4 45 16 66 10C87 4 108 16 129 10C150 4 171 16 192 10C213 4 234 16 255 10C273 5 289 13 307 9" stroke="#F28C1E" strokeWidth="4" strokeLinecap="round" />
                </svg>
              </span>
            </h1>

            {/* Action Pills */}
            <div className="hero-neo-pills-wrap">
              <div className="hero-neo-pills-row">
                <Link href="/arena" className="hero-neo-pill pill-peach">
                  <span className="pill-badge">02 · ARENA</span>
                  <span className="pill-text">Play.</span>
                </Link>
                <Link href="#developers" className="hero-neo-pill pill-blue">
                  <span className="pill-badge">DEVELOPERS</span>
                  <span className="pill-text">Explore.</span>
                </Link>
              </div>
              <div className="hero-neo-pills-row">
                <Link href="/tech-hub" className="hero-neo-pill pill-mint">
                  <span className="pill-badge">03 · NEWS</span>
                  <span className="pill-text">Stay Updated.</span>
                </Link>
                <span className="pill-orange-tab" aria-hidden="true" />
              </div>
            </div>

            {/* Description Copy */}
            <p className="hero-neo-copy">
              Create your professional developer portfolio, challenge your friends in live coding quizzes, and stay updated with the latest technology trends — all in one place.
            </p>

            {/* CTA Buttons */}
            <div className="hero-neo-buttons">
              <Link className="neo-btn neo-btn-orange" href="/builder/upload">
                Create Your Portfolio &rarr;
              </Link>
              <Link className="neo-btn neo-btn-white" href="/arena">
                Play with Friends
              </Link>
            </div>

            {/* Feature Checklist Tags */}
            <div className="hero-neo-checklist">
              <div className="checklist-row">
                <div className="checklist-item">
                  <span className="check-box check-blue" />
                  <span>Build Your Portfolio</span>
                </div>
                <div className="checklist-item">
                  <span className="check-box check-orange" />
                  <span>Challenge Your Friends</span>
                </div>
              </div>
              <div className="checklist-row">
                <div className="checklist-item">
                  <span className="check-box check-green" />
                  <span>Discover Tech Trends</span>
                </div>
              </div>
            </div>

            {/* Covering Strip */}
            <div className="hero-neo-covering">
              <span className="covering-label">COVERING &rarr;</span>
              <div className="covering-tags">
                <Link href="/tech-hub" className="covering-tag">AI &amp; ML</Link>
                <Link href="/tech-hub" className="covering-tag">Programming</Link>
                <Link href="/tech-hub" className="covering-tag">Data Science</Link>
                <Link href="/tech-hub" className="covering-tag">Startups</Link>
                <Link href="/tech-hub" className="covering-tag">Developer Tools</Link>
                <Link href="/tech-hub" className="covering-tag">Cybersecurity</Link>
              </div>
            </div>


          </div>

          {/* Right Column: 3 Connected Browser Cards */}
          <div className="hero-neo-right">
            <div className="neo-showcase-board">
              {/* Card 1: 01 · PORTFOLIO */}
              <div className="neo-window window-portfolio">
                <div className="neo-window-badges">
                  <span className="win-badge badge-blue">01 · PORTFOLIO</span>
                  <span className="win-badge badge-yellow">unique URL + QR</span>
                </div>
                <div className="neo-window-header">
                  <div className="win-controls">
                    <span /><span /><span />
                  </div>
                  <div className="win-url">devportfolio.app/alex-johnson</div>
                </div>
                <div className="neo-window-body portfolio-body">
                  <div className="neo-profile-row">
                    <div className="neo-avatar">
                      <svg viewBox="0 0 44 44" className="neo-avatar-svg" aria-label="Alex Johnson">
                        <circle cx="22" cy="22" r="22" fill="#F28C1E" />
                        <ellipse cx="22" cy="18" rx="8" ry="10" fill="#9C6237" />
                        <path d="M14 15C14 9 18 6 22 6C26 6 30 9 30 15C30 17 29 18 28 17C26 12 24 10 22 10C20 10 18 12 16 17C15 18 14 17 14 15Z" fill="#12233B" />
                        <circle cx="19" cy="18" r="1.3" fill="#12233B" />
                        <circle cx="25" cy="18" r="1.3" fill="#12233B" />
                        <path d="M19 22C20.5 23.5 23.5 23.5 25 22" stroke="#12233B" strokeWidth="1.2" strokeLinecap="round" fill="none" />
                        <rect x="20" y="27" width="4" height="4" fill="#9C6237" />
                        <path d="M10 40C10 32 15 30 22 30C29 30 34 32 34 40" fill="#12233B" />
                      </svg>
                    </div>
                    <div className="neo-profile-info">
                      <h3 className="neo-profile-name">Alex Johnson</h3>
                      <p className="neo-profile-role">Full Stack Developer</p>
                      <span className="neo-badge-open">Open to work</span>
                    </div>
                  </div>

                  <div className="neo-chips-row">
                    <span>React</span>
                    <span>Node.js</span>
                    <span>Python</span>
                    <span>SQL</span>
                  </div>

                  <div className="neo-projects-grid">
                    <div className="neo-project-item">
                      <div className="neo-project-thumb thumb-orange">
                        <div className="thumb-circle-navy" />
                        <div className="thumb-bar" />
                      </div>
                      <span className="neo-project-name">DevPortfolio</span>
                    </div>
                    <div className="neo-project-item">
                      <div className="neo-project-thumb thumb-navy">
                        <div className="thumb-grid-dots">
                          {Array.from({ length: 15 }).map((_, i) => (
                            <i key={i} />
                          ))}
                        </div>
                        <div className="thumb-circle-yellow" />
                      </div>
                      <span className="neo-project-name">TaskFlow</span>
                    </div>
                  </div>

                  <div className="neo-portfolio-footer">
                    <div className="neo-social-icons">
                      <span className="neo-social-btn">Gh</span>
                      <span className="neo-social-btn">in</span>
                      <span className="neo-social-btn">X</span>
                    </div>
                    <div className="neo-qr-mini" aria-label="QR Code preview">
                      <svg viewBox="0 0 32 32" className="qr-svg" fill="#12233B">
                        <rect x="2" y="2" width="10" height="10" rx="1" fill="#12233B" />
                        <rect x="4" y="4" width="6" height="6" fill="#FFF" />
                        <rect x="5.5" y="5.5" width="3" height="3" fill="#12233B" />

                        <rect x="20" y="2" width="10" height="10" rx="1" fill="#12233B" />
                        <rect x="22" y="4" width="6" height="6" fill="#FFF" />
                        <rect x="23.5" y="5.5" width="3" height="3" fill="#12233B" />

                        <rect x="2" y="20" width="10" height="10" rx="1" fill="#12233B" />
                        <rect x="4" y="22" width="6" height="6" fill="#FFF" />
                        <rect x="5.5" y="23.5" width="3" height="3" fill="#12233B" />

                        <rect x="14" y="4" width="3" height="3" fill="#12233B" />
                        <rect x="14" y="10" width="3" height="3" fill="#12233B" />
                        <rect x="14" y="15" width="4" height="4" fill="#12233B" />
                        <rect x="20" y="15" width="4" height="3" fill="#12233B" />
                        <rect x="26" y="15" width="4" height="4" fill="#12233B" />
                        <rect x="14" y="22" width="3" height="4" fill="#12233B" />
                        <rect x="20" y="22" width="5" height="4" fill="#12233B" />
                        <rect x="26" y="24" width="4" height="5" fill="#12233B" />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>

              {/* Diagram Connector (Dashed lines + center circular pin) */}
              <div className="neo-diagram-connector" aria-hidden="true">
                <div className="connector-pin" />
                <div className="connector-line-v" />
                <div className="connector-branch-left" />
                <div className="connector-branch-top" />
                <div className="connector-branch-bottom" />
              </div>

              {/* Stacked Column: Arena & News */}
              <div className="neo-stacked-column">
                {/* Card 2: 02 · ARENA */}
                <div className="neo-window window-arena">
                  <div className="neo-window-badges">
                    <span className="win-badge badge-peach">02 · ARENA</span>
                    <span className="win-badge badge-yellow">timer + leaderboard</span>
                  </div>
                  <div className="neo-window-header">
                    <div className="win-controls">
                      <span /><span /><span />
                    </div>
                    <div className="win-title">Python Showdown · Room ARN-4F7K</div>
                  </div>
                  <div className="neo-window-body arena-body">
                    <div className="neo-arena-q-row">
                      <div className="neo-timer-circle">
                        <span>00:24</span>
                      </div>
                      <p className="neo-q-text">
                        What will be the output of len([1, 2, 3])?
                      </p>
                    </div>

                    <div className="neo-options-grid">
                      <div className="neo-opt">A. 2</div>
                      <div className="neo-opt opt-selected">B. 3</div>
                      <div className="neo-opt">C. 4</div>
                      <div className="neo-opt">D. Error</div>
                    </div>

                    <div className="neo-arena-scoreboard">
                      <div className="arena-score-player">
                        <div className="arena-player-avatar avatar-orange" />
                        <span className="arena-player-pts">225</span>
                      </div>
                      <div className="arena-vs-bar">
                        <div className="vs-bar-orange" style={{ width: '68%' }} />
                        <div className="vs-bar-blue" style={{ width: '32%' }} />
                      </div>
                      <div className="arena-score-player">
                        <span className="arena-player-pts">110</span>
                        <div className="arena-player-avatar avatar-blue" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Card 3: 03 · NEWS */}
                <div className="neo-window window-news">
                  <div className="neo-window-badges">
                    <span className="win-badge badge-mint">03 · NEWS</span>
                    <span className="win-badge badge-yellow">source + date</span>
                  </div>
                  <div className="neo-window-header">
                    <div className="win-controls">
                      <span /><span /><span />
                    </div>
                    <div className="win-title">Tech News · Today</div>
                  </div>
                  <div className="neo-window-body news-body">
                    <div className="neo-news-story">
                      <div className="news-thumb thumb-purple">
                        <div className="news-thumb-inner-card" />
                        <div className="news-thumb-inner-dot" />
                      </div>
                      <div className="news-details">
                        <span className="news-tag tag-ai">AI</span>
                        <h4 className="news-headline">Open-source model closes the gap with paid tools</h4>
                        <span className="news-meta">TechWire · 11 Nov</span>
                      </div>
                    </div>

                    <div className="news-divider" />

                    <div className="neo-news-story">
                      <div className="news-thumb thumb-tan">
                        <div className="news-target-ring ring-outer" />
                        <div className="news-target-ring ring-mid" />
                        <div className="news-target-ring ring-dot" />
                      </div>
                      <div className="news-details">
                        <span className="news-tag tag-tools">Dev Tools</span>
                        <h4 className="news-headline">A faster package manager for JavaScript</h4>
                        <span className="news-meta">Dev Daily · 11 Nov</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features section */}
      <section className="features">
        <div className="container feature-grid">
          {[
            [Code2, 'Create Portfolio', 'Build your professional portfolio with customizable templates and themes.', 'peach'],
            [Users, 'Discover Talent', 'Find skilled developers for your team or project with advanced filters.', 'blue'],
            [BriefcaseBusiness, 'Jobs & Freelance', 'Post jobs or freelance projects and connect with the right talent.', 'green'],
            [Grid2X2, 'Digital Identity Card', 'Share your profile with a QR code and one link, everywhere.', 'purple'],
          ].map(([Icon, title, copy, color]) => (
            <div className="feature" key={title as string}>
              <div className={`feature-icon ${color}`}>
                <Icon size={19} />
              </div>
              <h3>{title as string}</h3>
              <p>{copy as string}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Builder section */}
      <section className="builder" id="builder">
        <div className="container builder-grid">
          <div className="builder-copy">
            <span className="eyebrow-pill">Create in Minutes</span>
            <h2>Build a Portfolio That Gets You Hired</h2>
            <p>Use our easy-to-use builder to create a professional portfolio, add your resume, connect your accounts, and showcase your work — no coding required.</p>
            <ul>
              {[
                'Pre-designed templates',
                'Import from GitHub & resume',
                'Add coding profiles (LeetCode, HackerRank, Kaggle)',
                'Get a shareable link & QR code',
              ].map(x => (
                <li key={x}><Check size={15}/>{x}</li>
              ))}
            </ul>
            <Link className="button navy" href="/builder/upload">Start Building Now <ArrowRight size={15}/></Link>
          </div>
          <BuilderPreview />
        </div>
      </section>

      {/* Stats Band */}
      <section className="stats-band" style={{ backgroundColor: '#f8f7ee', backgroundImage: 'linear-gradient(to right, #e7e3d5 1.5px, transparent 1.5px), linear-gradient(to bottom, #e7e3d5 1.5px, transparent 1.5px)', backgroundSize: '30px 30px' }}>
        <div className="container stats-grid">
          {[
            ['10,000+', 'Developers'],
            ['500+', 'Hiring Partners'],
            ['2,000+', 'Jobs & Projects'],
            ['99%', 'Satisfaction Rate'],
          ].map(([n, l]) => (
            <div key={l}><b>{n}</b><span>{l}</span></div>
          ))}
        </div>
      </section>

      {/* CTA Band */}
      <section className="cta">
        <div className="container cta-inner">
          <div className="cta-art">
            <Character label="" tone="orange" />
            <Character label="" tone="navy" />
          </div>
          <div>
            <h2>Ready to showcase your talent?</h2>
            <p>Join thousands of developers and get discovered by top companies.</p>
          </div>
          <Link className="button orange" href="/builder/upload">Create Your Portfolio <ArrowRight size={15}/></Link>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ backgroundColor: '#0f1b2d', color: '#ffffff' }}>
        <div className="container footer-grid">
          <div>
            <Logo />
            <p>Build. Showcase. Get Hired.</p>
          </div>
          <div>
            <h4>Product</h4>
            <Link href="#builder">Create Portfolio</Link>
            <Link href="#developers">Find Developers</Link>
            <Link href="#jobs">Jobs & Freelance</Link>
            <Link href="#pricing">Pricing</Link>
          </div>
          <div>
            <h4>Company</h4>
            <Link href="#about">About Us</Link>
            <Link href="#blog">Blog</Link>
            <Link href="#contact">Contact</Link>
            <Link href="#privacy">Privacy Policy</Link>
          </div>
          <div>
            <h4>Follow Us</h4>
            <div className="socials">
              <a href="#github" aria-label="GitHub"><Code2 size={14}/></a>
              <a href="#linkedin" aria-label="LinkedIn"><Users size={14}/></a>
              <a href="#x" aria-label="X"><X size={14}/></a>
              <a href="#youtube" aria-label="YouTube"><Sparkles size={14}/></a>
            </div>
          </div>
        </div>
        <div className="container copyright">© 2026 Crafdeck. All rights reserved.</div>
      </footer>
    </main>
  )
}
