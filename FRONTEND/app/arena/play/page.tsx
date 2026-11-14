'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Check, LogOut, Timer, Trophy } from 'lucide-react'
import { arenaWebSocketUrl, getArenaSession } from '../../../lib/arena-api'
import './play.css'
import './result.css'

type Question = {
  question_id: string
  index: number
  total: number
  question_text: string
  code_snippet: string
  options: { id: string; text: string }[]
  difficulty: string
  topic: string
  deadline_ms: number
  already_answered?: boolean
}

type Score = {
  user_id: string
  display_name: string
  score: number
  correct: number
  answered: number
  unanswered: number
  accuracy: number
  rank: number
}

type ServerMessage = { type: string; payload?: any }
type CompletedMatch = {
  winner_id: string | null
  is_draw: boolean
  scoreboard: Score[]
}

function Chip({ children, tone = '' }: { children: React.ReactNode; tone?: string }) {
  return <span className={`match-chip ${tone}`}>{children}</span>
}

function Avatar({ variant = 'alex' }: { variant?: 'alex' | 'riya' }) {
  return <div className={`match-avatar ${variant}`}><div className="avatar-face" /><div className="avatar-shirt" /></div>
}

function PlayContent() {
  const params = useSearchParams()
  const router = useRouter()
  const room = params.get('room') || ''
  const roomId = params.get('roomId')
  const socketRef = useRef<WebSocket | null>(null)
  const [question, setQuestion] = useState<Question | null>(null)
  const [scores, setScores] = useState<Score[]>([])
  const [answer, setAnswer] = useState<string | null>(null)
  const [answered, setAnswered] = useState(false)
  const [correctOption, setCorrectOption] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState<CompletedMatch | null>(null)
  const [userId, setUserId] = useState('')
  const [matchSeconds, setMatchSeconds] = useState(0)

  useEffect(() => {
    if (!roomId) {
      setError('This match link is missing its room id.')
      return
    }
    let cancelled = false
    getArenaSession().then(session => {
      if (cancelled) return
      setUserId(session.user_id)
      const socket = new WebSocket(arenaWebSocketUrl(roomId, session.access_token))
      socketRef.current = socket
      socket.onopen = () => socket.send(JSON.stringify({ type: 'room.ready', payload: { ready: true } }))
      socket.onmessage = event => {
        const message = JSON.parse(event.data) as ServerMessage
        const payload = message.payload
        if (message.type === 'match.question' || message.type === 'match.state' && payload?.current_question) {
          setQuestion(message.type === 'match.question' ? payload : payload.current_question)
          setAnswer(null)
          setAnswered(Boolean(payload.already_answered))
          setCorrectOption(null)
        }
        if (message.type === 'match.state' && payload?.scoreboard) setScores(payload.scoreboard)
        if (message.type === 'match.score_update') setScores(payload.scoreboard)
        if (message.type === 'match.answer_result') setCorrectOption(payload.correct_option)
        if (message.type === 'match.started') setMatchSeconds(0)
        if (message.type === 'match.completed') {
          setScores(payload.scoreboard || [])
          setCompleted(payload)
        }
        if (message.type === 'match.error') setError(payload?.message || 'Match request failed')
      }
      socket.onerror = () => setError('Unable to connect to the Arena match.')
    }).catch(value => setError(value instanceof Error ? value.message : 'Unable to start the match.'))
    return () => {
      cancelled = true
      socketRef.current?.close()
    }
  }, [roomId])

  useEffect(() => {
    if (completed) return
    const timer = window.setInterval(() => setMatchSeconds(value => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [completed])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (question) setSeconds(Math.max(0, Math.ceil((question.deadline_ms - Date.now()) / 1000)))
    }, 250)
    return () => window.clearInterval(timer)
  }, [question])

  const me = scores.find(score => score.user_id === userId)
  const opponent = scores.find(score => score.user_id !== userId)
  const selectedText = useMemo(() => question?.options.find(option => option.id === answer)?.text, [question, answer])

  const submitAnswer = (option: string) => {
    if (!question || answered || correctOption) return
    setAnswer(option)
    setAnswered(true)
    socketRef.current?.send(JSON.stringify({
      type: 'match.answer',
      payload: { question_id: question.question_id, option, request_id: crypto.randomUUID() },
    }))
  }

  if (completed) {
    return <ResultPage completed={completed} userId={userId} matchSeconds={matchSeconds} />
  }

  return <main className="match-page">
    <header className="match-topbar"><div className="match-top-inner"><Link href="/arena" className="match-brand"><span>&lt;/&gt;</span><b>Coding Arena</b></Link><i className="match-divider" /><b className="match-title">Live Match</b><Chip tone="peach">Room {room || '—'}</Chip><div className="match-actions"><span className="live-pill"><i />LIVE</span><button className="exit-button" onClick={() => router.push('/arena')}><LogOut size={14} /> Exit Match</button></div></div></header>
    <div className="match-shell">
      {error && <p className="match-error" role="alert">{error}</p>}
      {!question && <section className="question-card match-loading"><Timer size={22} /> Waiting for the match to start…</section>}
      {question && <><section className="match-status"><div><small>Question</small><strong>{question.index + 1} <em>/ {question.total}</em></strong><div className="status-progress"><i style={{ width: `${((question.index + 1) / question.total) * 100}%` }} /></div></div><div className="timer-ring"><b>00:{String(seconds).padStart(2, '0')}</b></div><div><small>Topic</small><strong>{question.topic}</strong></div><div><small>Your score</small><strong>{me?.score ?? 0} <em>pts</em></strong></div></section>
        <section className="players-row"><Player player={me} you variant="alex" /><div className="versus"><b>VS</b><strong>{me && opponent ? `${Math.abs(me.score - opponent.score)} point gap` : 'Match in progress'}</strong><span>{me?.correct ?? 0} correct · {opponent?.correct ?? 0} correct</span></div><Player player={opponent} variant="riya" /></section>
        <div className="match-grid"><div className="match-main"><section className="question-card"><div className="question-chips"><Chip tone="peach">Question {question.index + 1}</Chip><Chip>{question.topic}</Chip><Chip tone="peach">{question.difficulty}</Chip></div><h1>{question.question_text}</h1>{question.code_snippet && <pre><code>{question.code_snippet}</code></pre>}<p className="hint">Choose one answer: A, B, C or D.</p><div className="options" role="radiogroup" aria-label="Answer options">{question.options.map(option => <button key={option.id} className={`option ${answer === option.id ? 'selected' : ''} ${correctOption === option.id ? 'correct' : ''}`} onClick={() => submitAnswer(option.id)} role="radio" aria-checked={answer === option.id}><b>{option.id}</b><strong>{option.text}</strong>{correctOption === option.id && <Check size={16} />}</button>)}</div>{selectedText && <p className="hint">Answer submitted. Waiting for the reveal…</p>}</section></div><aside className="match-side"><SideCard title="Live scoreboard">{scores.map(score => <div className="score-row" key={score.user_id}><b>{score.rank}</b><Avatar variant={score.user_id === me?.user_id ? 'alex' : 'riya'} /><strong>{score.display_name}</strong><span>{score.accuracy}%</span><em>{score.score}</em></div>)}</SideCard></aside></div></>}
    </div>
  </main>
}

function ResultPage({ completed, userId, matchSeconds }: { completed: CompletedMatch; userId: string; matchSeconds: number }) {
  const mine = completed.scoreboard.find(score => score.user_id === userId)
  const opponent = completed.scoreboard.find(score => score.user_id !== userId)
  const mineScore = numeric(mine?.score)
  const opponentScore = numeric(opponent?.score)
  const mineCorrect = numeric(mine?.correct)
  const mineAnswered = numeric(mine?.answered)
  const mineUnanswered = numeric(mine?.unanswered)
  const mineAccuracy = numeric(mine?.accuracy)
  const won = !completed.is_draw && completed.winner_id === userId
  const lost = !completed.is_draw && !won
  const result = completed.is_draw ? 'Draw' : won ? 'Victory' : 'Defeat'
  const difference = Math.abs(mineScore - opponentScore)
  const formatTime = (value: number) => `${String(Math.floor(numeric(value) / 60)).padStart(2, '0')}:${String(numeric(value) % 60).padStart(2, '0')}`

  return <main className="match-page result-page">
    <div className="match-shell result-shell">
      <section className={`result-hero ${won ? 'winner' : lost ? 'loser' : 'draw'}`}>
        <span className="result-badge">Match complete</span>
        <div className="result-avatar"><Avatar variant={won || completed.is_draw ? 'alex' : 'riya'} /></div>
        <h1>{completed.is_draw ? 'Match drawn' : `${mine?.display_name || 'Player'} ${won ? 'wins!' : 'lost'}`}</h1>
        <div className="result-versus">
          <div><small>{mine?.display_name || 'You'}</small><strong>{mineScore}</strong></div>
          <b>VS</b>
          <div><small>{opponent?.display_name || 'Opponent'}</small><strong>{opponentScore}</strong></div>
        </div>
        <p>{completed.is_draw ? 'Both players finished with the same score.' : `Points difference: ${difference}`}</p>
      </section>
      <section className="result-stats">
        <ResultStat label="Correct" value={mineCorrect} />
        <ResultStat label="Incorrect" value={Math.max(0, mineAnswered - mineCorrect)} />
        <ResultStat label="Unanswered" value={mineUnanswered} />
        <ResultStat label="Accuracy" value={`${mineAccuracy}%`} />
        <ResultStat label="Total time" value={formatTime(matchSeconds)} />
        <ResultStat label="Points difference" value={`${won ? '+' : lost ? '-' : ''}${difference}`} />
      </section>
      <section className="final-rankings">
        <h2>Final rankings</h2>
        <div className="ranking-head"><span>Rank</span><span>Player</span><span>Score</span><span>Correct</span><span>Incorrect</span><span>Unanswered</span><span>Accuracy</span><span>Time</span><span>Diff</span></div>
        {completed.scoreboard.map((score, index) => {
          const isWinner = completed.winner_id === score.user_id
          const isMe = score.user_id === userId
          const scoreDifference = numeric(score.score) - mineScore
          return <div className={`ranking-row ${isWinner ? 'ranking-winner' : completed.is_draw ? '' : 'ranking-loser'}`} key={score.user_id}>
            <span>{index + 1}</span><strong><span className={`ranking-avatar ${isWinner ? 'green' : 'red'}`} />{score.display_name}{isMe && ' (You)'}</strong><span>{numeric(score.score)}</span><span>{numeric(score.correct)}</span><span>{Math.max(0, numeric(score.answered) - numeric(score.correct))}</span><span>{numeric(score.unanswered)}</span><span>{numeric(score.accuracy)}%</span><span>{formatTime(matchSeconds)}</span><span>{scoreDifference > 0 ? '+' : ''}{scoreDifference}</span>
          </div>
        })}
      </section>
      <div className="result-actions"><Link className="orange-button" href="/arena">Rematch with Same Friends</Link><Link className="secondary-button" href="/arena">View Detailed Results</Link><Link className="dark-button" href="/arena"><Trophy size={15} /> Return to Coding Arena</Link></div>
      <span className="result-label" aria-label={result}>{result}</span>
    </div>
  </main>
}

function numeric(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function ResultStat({ label, value }: { label: string; value: string | number }) {
  return <div className="result-stat"><strong>{value}</strong><small>{label}</small></div>
}

function Player({ player, you, variant }: { player?: Score; you?: boolean; variant: 'alex' | 'riya' }) {
  return <div className={`player-card ${you ? 'you' : ''}`}><Avatar variant={variant} /><div><h2>{player?.display_name || 'Waiting…'} {you && <Chip>You</Chip>}</h2><p>{player?.correct ?? 0} correct · Rank #{player?.rank ?? '—'}</p></div><strong>{player?.score ?? 0}<small>points</small></strong></div>
}

function SideCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="side-card"><h2>{title}</h2>{children}</section>
}

export default function PlayPage() {
  return <Suspense fallback={<main className="match-page"><div className="match-shell"><p className="match-loading">Loading match…</p></div></main>}><PlayContent /></Suspense>
}
