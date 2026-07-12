import Navbar from "@/components/Navbar";
import AuthCta from "@/components/AuthCta";
import styles from "./page.module.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ResumeAI — AI-Powered Resume Optimizer",
  description:
    "Upload your resume and get instant AI-powered analysis. Extract text, count pages, and optimize your resume for any job — for free.",
};

const features = [
  {
    icon: "⚡",
    title: "Instant Parsing",
    desc: "PDF and DOCX resumes are parsed in seconds with full text extraction.",
  },
  {
    icon: "🔒",
    title: "Secure & Private",
    desc: "Your resume is stored securely with Firebase Auth protecting every request.",
  },
  {
    icon: "📊",
    title: "Clear Parsing Results",
    desc: "Review extracted text, page count, and document details before analysis.",
  },
  {
    icon: "🤖",
    title: "Job Matching",
    desc: "Compare a saved resume with a job description and review strengths, gaps, and keywords.",
  },
];

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <Navbar />

      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.heroBg} aria-hidden />
        <div className={`container ${styles.heroContent}`}>
          <div className={`${styles.badge} animate-fade-in`}>
            <span className={styles.badgeDot} />
            Secure Resume Parsing
          </div>
          <h1 className={`${styles.headline} animate-slide-up`}>
            Turn Your Resume Into{" "}
            <span className="gradient-text">Structured Text</span>
          </h1>
          <p className={`${styles.subheadline} animate-slide-up`}>
            Upload any PDF or DOCX resume and get instant text extraction,
            secure parsing, and reviewable output ready for job matching.
          </p>
          <div className={`${styles.ctas} animate-slide-up`}>
            <AuthCta id="hero-cta-btn" className="btn btn-primary btn-lg" guestLabel="Get started free">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </AuthCta>
            <AuthCta className="btn btn-ghost btn-lg" guestLabel="Sign in" />
          </div>
        </div>

        {/* Floating card preview */}
        <div className={`container ${styles.previewContainer}`}>
          <div className={`glass-card ${styles.previewCard}`}>
            <div className={styles.previewHeader}>
              <div className={styles.previewDots}>
                <span style={{ background: "#f43f5e" }} />
                <span style={{ background: "#f59e0b" }} />
                <span style={{ background: "#10b981" }} />
              </div>
              <span className={styles.previewTitle}>resume_analysis.json</span>
            </div>
            <pre className={styles.previewCode}>{`{
  "resume_id": "a1b2c3d4-...",
  "filename": "john_doe_resume.pdf",
  "file_type": "pdf",
  "page_count": 2,
  "character_count": 4821,
  "text": "John Doe\\nSoftware Engineer\\n..."
}`}</pre>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className={styles.features}>
        <div className="container">
          <div className={styles.featuresHeader}>
            <h2 className={styles.featuresTitle}>
              Everything you need to <span className="gradient-text">stand out</span>
            </h2>
            <p className={styles.featuresSubtitle}>
              A reliable foundation for resume analysis and job matching.
            </p>
          </div>
          <div className={styles.featuresGrid}>
            {features.map((f, i) => (
              <div
                key={f.title}
                className={`glass-card ${styles.featureCard}`}
                style={{ animationDelay: `${i * 0.1}s` }}
              >
                <div className={styles.featureIcon}>{f.icon}</div>
                <h3 className={styles.featureTitle}>{f.title}</h3>
                <p className={styles.featureDesc}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section className={styles.ctaBanner}>
        <div className="container">
          <div className={`glass-card ${styles.ctaCard}`}>
            <h2 className={styles.ctaTitle}>
              Ready to optimize your resume?
            </h2>
            <p className={styles.ctaDesc}>
              Parse your resume now and prepare it for tailored job analysis.
            </p>
            <AuthCta
              id="cta-banner-btn"
              className="btn btn-primary btn-lg"
              guestLabel="Start for free"
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <p className={styles.footerText}>
            © {new Date().getFullYear()} ResumeAI.
          </p>
        </div>
      </footer>
    </div>
  );
}
