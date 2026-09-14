import React from 'react';
import { AlertTriangle, RefreshCw, ShieldAlert } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ABPS ErrorBoundary Caught Exception]:', error, errorInfo);
    this.setState({ errorInfo });
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallbackRender) {
        return this.props.fallbackRender({
          error: this.state.error,
          resetErrorBoundary: this.handleReset
        });
      }

      const isMapVariant = this.props.variant === 'map';
      const safeErrorMessage = this.state.error?.message || 'An unexpected rendering error occurred.';

      if (isMapVariant) {
        return (
          <div className="cris-panel overflow-hidden border-2 border-red-300 bg-red-50/50 shadow-sm p-4 my-2">
            <div className="flex items-start space-x-3">
              <div className="p-2 bg-red-100 rounded text-red-700">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="flex-1 space-y-2">
                <div className="border-b border-red-200 pb-2">
                  <h3 className="text-xs font-black uppercase tracking-wider text-red-900 flex items-center gap-1.5">
                    RAILWAY MAP ERROR
                  </h3>
                  <p className="text-xs text-red-800 font-medium mt-0.5">
                    Unable to render the railway map.
                  </p>
                </div>

                <div className="bg-white p-2.5 rounded border border-red-200 text-xs font-mono text-red-900 space-y-1">
                  <span className="font-bold text-[10px] text-slate-500 uppercase block">Technical details:</span>
                  <p className="break-all">{safeErrorMessage}</p>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <button
                    type="button"
                    onClick={this.handleReset}
                    className="cris-btn cris-btn-secondary text-xs flex items-center gap-1.5 bg-white hover:bg-slate-100 border-red-300 text-red-900 font-bold"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Retry Map
                  </button>
                  <span className="text-[11px] text-slate-600 italic">
                    The rest of the application remains available.
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
      }

      // Default Generic / Page Fallback
      return (
        <div className="p-4 m-3 bg-white border border-red-200 shadow-sm rounded-md space-y-3">
          <div className="flex items-center space-x-2 text-red-800">
            <ShieldAlert className="w-5 h-5 text-red-600" />
            <h2 className="text-sm font-bold uppercase">Component Error Detected</h2>
          </div>
          <p className="text-xs text-slate-600">
            {this.props.fallbackMessage || 'This section encountered an error while rendering, but the rest of the application is functioning.'}
          </p>
          <div className="bg-slate-50 p-2.5 rounded border text-[11px] font-mono text-slate-800">
            {safeErrorMessage}
          </div>
          <button
            type="button"
            onClick={this.handleReset}
            className="cris-btn cris-btn-primary text-xs flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reload Section
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
