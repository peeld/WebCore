import { Component } from 'react'
import { captureError } from '../utils/logger'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    captureError(error, { componentStack: info.componentStack }, 'react')
  }

  render() {
    if (this.state.hasError) {
      return (
        <section className="section">
          <div className="container has-text-centered">
            <p className="title is-4">Something went wrong.</p>
            <p className="subtitle">
              Please refresh the page. If the problem persists, contact support.
            </p>
            <button className="button is-primary" onClick={() => this.setState({ hasError: false })}>
              Try again
            </button>
          </div>
        </section>
      )
    }
    return this.props.children
  }
}
