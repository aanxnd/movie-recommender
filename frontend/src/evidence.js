// Presentation heuristic, not a calibrated likelihood or a CF admission rule.
export function evidenceMessage(movies) {
  const predictions = movies.filter((movie) => movie.method === 'collaborative_filtering')
  return predictions.length && predictions.every((movie) => movie.confidence < 0.1)
    ? 'Limited recommendation evidence. These estimates may stay close to your average rating. Rate more movies with varied ratings, or choose Popular for historical favorites.'
    : ''
}
