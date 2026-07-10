export default function Modal({ title, onClose, children, wide = false }) {
  return (
    <div className="modal-backdrop">
      <div className={`modal-card ${wide ? 'modal-card-wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
