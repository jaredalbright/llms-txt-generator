import Layout from './components/Layout';
import URLInput from './components/URLInput';
import ProgressView from './components/ProgressView';
import EditorPreview from './components/EditorPreview';
import RepromptBar from './components/RepromptBar';
import ExportBar from './components/ExportBar';
import { useJob } from './hooks/useJob';

export default function App() {
  const {
    submitJob,
    regenerate,
    reprompt,
    markdown,
    setMarkdown,
    status,
    progress,
    error,
    isReprompting,
  } = useJob();

  const isLoading = status === 'crawling' || status === 'processing' || status === 'pending';
  const isComplete = status === 'completed' && markdown;

  return (
    <Layout>
      <div className="space-y-6">
        {/* URL Input */}
        <URLInput onSubmit={(url, clientInfo) => submitJob(url, clientInfo)} disabled={isLoading} />

        {/* Error display */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Progress */}
        {isLoading && status && (
          <ProgressView
            status={status}
            pagesFound={progress?.pages_found}
            message={progress?.message}
          />
        )}

        {/* Editor + Preview */}
        {isComplete && (
          <>
            <EditorPreview markdown={markdown} onChange={setMarkdown} />

            {/* Reprompt */}
            <RepromptBar onSubmit={reprompt} disabled={isReprompting} />

            {/* Export */}
            <ExportBar markdown={markdown} onRegenerate={regenerate} />
          </>
        )}
      </div>
    </Layout>
  );
}
