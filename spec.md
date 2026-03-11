# Voice-Based Interview Agent

**System Design Specification (spec.md)**

---

# 1. Introduction

This document specifies the architecture and behavior of a **Voice-Based Interview Agent** that conducts structured interviews with candidates. The system interacts with candidates through voice, dynamically generates interview questions, evaluates answers using an AI model, and produces a final report summarizing the interview.

The goal of the system is to simulate a human interviewer by:

* Asking domain-relevant questions
* Evaluating candidate responses
* Adapting question difficulty
* Recording interview interactions
* Generating a final interview report

The design focuses on **modularity, scalability, and extensibility**, allowing the interview agent to evolve into a full recruitment platform.

---

# 2. System Objectives

The system aims to:

1. Conduct voice-based interviews.
2. Dynamically generate interview questions.
3. Evaluate candidate responses using AI.
4. Adapt the interview flow based on performance.
5. Record interview interactions.
6. Generate a final structured interview report.

---

# 3. High-Level System Flow

The system operates as an interactive loop.

1. Candidate speaks a response.
2. Speech is converted into text.
3. The interview agent processes the answer.
4. The answer evaluator scores the response.
5. The system records the question-answer pair.
6. The agent determines the next question.
7. The question is converted to speech and presented to the candidate.

After the interview ends, a **report is generated** summarizing the candidate’s performance.

High-level architecture flow:

```id="q9n6km"
Candidate Voice
      ↓
Speech-to-Text
      ↓
Conversation Session Manager
      ↓
Interview Agent
      ↓
Answer Evaluator
      ↓
Interview Record Storage
      ↓
Next Question Generator
      ↓
Text-to-Speech
      ↓
Candidate hears next question
```

When the interview finishes:

```id="l5vsl2"
Interview Complete
      ↓
Report Generator
      ↓
Interview Report
```

---

# 4. Core Components

## 4.1 Voice Interface

The Voice Interface handles communication with the candidate.

Responsibilities:

* Capture microphone input
* Send audio to Speech-to-Text engine
* Receive generated responses
* Convert responses to audio

Technologies may include:

* WebRTC
* Whisper
* ElevenLabs / Coqui TTS

---

## 4.2 Speech Processing Layer

Responsible for converting audio into text and vice versa.

Pipeline:

```id="6mhoh7"
Audio Input
   ↓
Speech-to-Text Engine
   ↓
Text Processing
   ↓
Text-to-Speech Engine
   ↓
Audio Output
```

---

## 4.3 Conversation Session Manager

Maintains the context of the interview conversation.

Responsibilities:

* Track session state
* Maintain conversation history
* Store the active interview session

Example session structure:

```id="m3tf6u"
ConversationSession
{
 sessionId
 startTime
 conversationHistory
 activeInterview
}
```

---

## 4.4 Interview Agent

The Interview Agent controls the interview logic.

Responsibilities:

* Generate interview questions
* Evaluate answers
* Adapt question difficulty
* Track interview progress

Core functions:

```id="s0f3p6"
generateQuestion()
evaluateAnswer()
decideNextStep()
endInterview()
```

---

## 4.5 Question Generator

Produces interview questions based on skill areas and difficulty levels.

Difficulty levels:

* Beginner
* Intermediate
* Advanced

Example structure:

```id="sg59y2"
InterviewQuestion
{
 questionId
 skill
 difficulty
 text
}
```

---

## 4.6 Answer Evaluator

Analyzes candidate responses and assigns a score using an evaluation rubric.

Evaluation criteria may include:

* correctness
* completeness
* clarity
* depth of explanation

Example output:

```id="2bf6av"
EvaluationResult
{
 score
 feedback
 strengths
 weaknesses
}
```

---

## 4.7 Interview Record Manager

Stores each question-answer interaction during the interview.

Example record:

```id="aapeg9"
InterviewRecord
{
 question
 candidateAnswer
 evaluationResult
 timestamp
}
```

This enables complete reconstruction of the interview conversation.

---

## 4.8 Report Generator

The Report Generator creates the final interview report.

Responsibilities:

* Retrieve all interview records
* Compile questions and answers
* Calculate total scores
* Summarize candidate performance
* Export report

Core operations:

```id="uy85oq"
generateReport()
compileResults()
calculateFinalScore()
exportReport()
```

---

# 5. Class Diagram

The class diagram defines the structure of the interview system.

```id="yhdjgi"
+-----------------------+
| ConversationSession   |
+-----------------------+
| sessionId             |
| startTime             |
| conversationHistory   |
| activeInterview       |
+-----------------------+
| addMessage()          |
| endSession()          |
+-----------+-----------+
            |
            | manages
            v
+-----------------------+
| InterviewSession      |
+-----------------------+
| interviewId           |
| candidate             |
| questionsAsked        |
| records               |
| totalScore            |
+-----------------------+
| startInterview()      |
| addRecord()           |
| endInterview()        |
+-----------+-----------+
            |
            | associated with
            v
+-----------------------+
| CandidateProfile      |
+-----------------------+
| candidateId           |
| name                  |
| email                 |
| experienceLevel       |
| skillScores           |
+-----------------------+

+-----------------------+
| InterviewAgent        |
+-----------------------+
| agentId               |
| role                  |
+-----------------------+
| generateQuestion()    |
| evaluateAnswer()      |
| decideNextStep()      |
+-----------+-----------+
            |
            | uses
            v
+-----------------------+
| QuestionGenerator     |
+-----------------------+
| difficultyLevels      |
+-----------------------+
| createQuestion()      |
+-----------+-----------+
            |
            v
+-----------------------+
| InterviewQuestion     |
+-----------------------+
| questionId            |
| skill                 |
| difficulty            |
| text                  |
+-----------------------+

+-----------------------+
| AnswerEvaluator       |
+-----------------------+
| scoringRubric         |
+-----------------------+
| evaluate()            |
+-----------+-----------+
            |
            v
+-----------------------+
| EvaluationResult      |
+-----------------------+
| score                 |
| feedback              |
| strengths             |
| weaknesses            |
+-----------------------+

+-----------------------+
| InterviewRecord       |
+-----------------------+
| question              |
| candidateAnswer       |
| evaluationResult      |
| timestamp             |
+-----------------------+

+-----------------------+
| ReportGenerator       |
+-----------------------+
| generateReport()      |
| summarizePerformance()|
+-----------+-----------+
            |
            v
+-----------------------+
| InterviewReport       |
+-----------------------+
| reportId              |
| candidate             |
| questionsAndAnswers   |
| totalScore            |
| strengths             |
| weaknesses            |
+-----------------------+
```

---

# 6. Class Associations

### ConversationSession → InterviewSession

A conversation session manages an interview session.

```id="n6rc2n"
ConversationSession (1) ----- (1) InterviewSession
```

---

### InterviewSession → CandidateProfile

Each interview session corresponds to one candidate.

```id="zq8s3m"
InterviewSession (1) ----- (1) CandidateProfile
```

---

### InterviewSession → InterviewRecord

An interview session contains multiple records.

```id="p2bts9"
InterviewSession (1) ----- (1..*) InterviewRecord
```

---

### InterviewRecord → InterviewQuestion

Each record contains one interview question.

```id="6qap2g"
InterviewRecord (1) ----- (1) InterviewQuestion
```

---

### InterviewRecord → EvaluationResult

Each record stores one evaluation result.

```id="mvyja9"
InterviewRecord (1) ----- (1) EvaluationResult
```

---

### InterviewAgent → QuestionGenerator

The interview agent delegates question generation.

```id="qqhwhd"
InterviewAgent ---- uses ----> QuestionGenerator
```

---

### InterviewAgent → AnswerEvaluator

The interview agent uses the evaluator to score responses.

```id="3m3vfi"
InterviewAgent ---- uses ----> AnswerEvaluator
```

---

### ReportGenerator → InterviewSession

The report generator reads interview session data.

```id="d9ktk7"
ReportGenerator ---- uses ----> InterviewSession
```

---

### ReportGenerator → InterviewReport

The report generator produces the final report.

```id="qyd1xq"
ReportGenerator ---- creates ----> InterviewReport
```

---

# 7. Sequence Diagram – Interview Interaction

The following sequence describes a candidate answering a question.

```id="n7it9a"
Candidate
   |
   | speaks answer
   v
VoiceInterface
   |
Speech-to-Text
   |
ConversationSession
   |
InterviewAgent
   |
AnswerEvaluator
   |
EvaluationResult
   |
InterviewSession (store record)
   |
InterviewAgent
   |
QuestionGenerator
   |
InterviewQuestion
   |
Text-to-Speech
   |
Candidate hears question
```

This interaction repeats for each interview question.

---

# 8. Sequence Diagram – Report Generation

When the interview finishes:

```id="ggdy7h"
InterviewAgent
   |
endInterview()
   |
ReportGenerator
   |
generateReport()
   |
InterviewSession (retrieve records)
   |
InterviewReport
   |
Store in Database
   |
Return Report
```

---

# 9. Interview State Lifecycle

The interview process follows a state machine.

```id="wcr94k"
Interview Start
      ↓
Ask Question
      ↓
Candidate Response
      ↓
Evaluate Answer
      ↓
Store Record
      ↓
Generate Next Question
      ↓
Repeat
      ↓
Interview Complete
      ↓
Generate Report
```

---

# 10. Data Storage

The system stores persistent interview data.

Example tables:

```id="7tqffk"
candidates
interview_sessions
interview_records
evaluation_results
interview_reports
conversation_logs
```

Recommended technologies:

* PostgreSQL
* Redis for session caching

---

# 11. Extensibility

The system design supports future extensions such as:

* coding interview evaluation
* system design interview modules
* automated candidate ranking
* recruiter dashboards
* integration with HR platforms

---

# 12. Summary

The Voice-Based Interview Agent system provides:

* Structured AI-driven interviews
* Adaptive question generation
* Automated answer evaluation
* Complete interview recording
* Automated report generation

The modular architecture separates **conversation management, interview logic, evaluation, and reporting**, ensuring maintainability and extensibility for future recruitment automation systems.
