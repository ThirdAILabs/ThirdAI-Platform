import React, { useEffect } from "react";

/**
 * Hook that alerts clicks outside of the passed ref
 */
export default function useClickOutside(
    ref: React.MutableRefObject<HTMLElement | null>,
    onClickOutside: () => void,
) {
    useEffect(() => {
        /**
         * Alert if clicked on outside of element
         */
        function handleClickOutside(event: any) {
            if (ref.current && !ref.current.contains(event.target)) {
                onClickOutside();
            }
        }
        // Bind the event listener
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            // Unbind the event listener on clean up
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [ref, onClickOutside]);
}
